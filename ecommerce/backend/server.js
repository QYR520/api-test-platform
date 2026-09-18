const express = require('express');
const cors = require('cors');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const app = express();
const PORT = 3000;

// 数据文件路径
const DATA_DIR = path.join(__dirname, 'data');
const USERS_FILE = path.join(DATA_DIR, 'users.json');
const PRODUCTS_FILE = path.join(DATA_DIR, 'products.json');
const CARTS_FILE = path.join(DATA_DIR, 'carts.json');
const ORDERS_FILE = path.join(DATA_DIR, 'orders.json');

// 中间件
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, '..', 'frontend')));

// ==================== 工具函数（内存模式，避免Windows EPERM）====================
function generateId() {
  return crypto.randomUUID();
}

// 内存数据库
let _users = [], _products = [], _carts = [], _orders = [];

function initData() {
  try { _users = JSON.parse(fs.readFileSync(USERS_FILE, 'utf-8')); } catch { _users = []; }
  try { _products = JSON.parse(fs.readFileSync(PRODUCTS_FILE, 'utf-8')); } catch { _products = []; }
  try { _carts = JSON.parse(fs.readFileSync(CARTS_FILE, 'utf-8')); } catch { _carts = []; }
  try { _orders = JSON.parse(fs.readFileSync(ORDERS_FILE, 'utf-8')); } catch { _orders = []; }
  console.log(`数据加载: ${_users.length}用户 ${_products.length}商品 ${_carts.length}购物车 ${_orders.length}订单`);
}

function trySave(filePath, data) {
  try { fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf-8'); } catch (e) { /* ignore */ }
}

// 读：从内存
function getUsers() { return _users; }
function getProducts() { return _products; }
function getCarts() { return _carts; }
function getOrders() { return _orders; }
function saveUsers() { trySave(USERS_FILE, _users); }
function saveCarts() { trySave(CARTS_FILE, _carts); }
function saveOrders() { trySave(ORDERS_FILE, _orders); }

// 启动时加载数据
initData();

// 认证中间件：验证 token
function auth(req, res, next) {
  const token = (req.headers.authorization || '').replace('Bearer ', '');
  if (!token) {
    return res.status(401).json({ code: 1, message: '请先登录' });
  }
  const users = getUsers();
  const user = users.find(u => u.token === token);
  if (!user) {
    return res.status(401).json({ code: 1, message: '登录已过期，请重新登录' });
  }
  req.user = user;
  next();
}

// ==================== 用户模块 ====================

// POST /api/register - 注册
app.post('/api/register', (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) {
    return res.status(400).json({ code: 1, message: '用户名和密码不能为空' });
  }
  if (username.trim().length < 3) {
    return res.status(400).json({ code: 1, message: '用户名至少3个字符' });
  }
  if (password.length < 4) {
    return res.status(400).json({ code: 1, message: '密码至少4个字符' });
  }

  const users = getUsers();
  if (users.find(u => u.username === username.trim())) {
    return res.status(400).json({ code: 1, message: '用户名已存在' });
  }

  const user = {
    id: generateId(),
    username: username.trim(),
    password,
    token: generateId(),
    createdAt: new Date().toISOString(),
  };
  users.push(user);
  saveUsers();

  res.status(201).json({
    code: 0,
    data: { id: user.id, username: user.username, token: user.token },
  });
});

// POST /api/login - 登录
app.post('/api/login', (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) {
    return res.status(400).json({ code: 1, message: '用户名和密码不能为空' });
  }

  const users = getUsers();
  const user = users.find(u => u.username === username.trim() && u.password === password);
  if (!user) {
    return res.status(400).json({ code: 1, message: '用户名或密码错误' });
  }

  // 重新生成 token（写文件失败时 fallback 到原 token）
  user.token = generateId();
  saveUsers();

  res.json({
    code: 0,
    data: { id: user.id, username: user.username, token: user.token },
  });
});

// ==================== 商品模块 ====================

// GET /api/products - 获取商品列表
app.get('/api/products', (req, res) => {
  const products = getProducts();
  res.json({ code: 0, data: products });
});

// ==================== 购物车模块（需登录）====================

// GET /api/cart - 获取购物车
app.get('/api/cart', auth, (req, res) => {
  const carts = getCarts();
  const products = getProducts();

  const myCart = carts
    .filter(c => c.userId === req.user.id)
    .map(c => {
      const product = products.find(p => p.id === c.productId);
      return {
        ...c,
        productName: product ? product.name : '未知商品',
        productImage: product ? product.image : '❓',
        productPrice: product ? product.price : 0,
        productStock: product ? product.stock : 0,
      };
    });

  res.json({ code: 0, data: myCart });
});

// POST /api/cart - 添加到购物车
app.post('/api/cart', auth, (req, res) => {
  const { productId, quantity = 1 } = req.body;
  const qty = parseInt(quantity);

  if (!productId || qty < 1) {
    return res.status(400).json({ code: 1, message: '参数错误' });
  }

  const products = getProducts();
  const product = products.find(p => p.id === parseInt(productId));
  if (!product) {
    return res.status(404).json({ code: 1, message: '商品不存在' });
  }
  if (qty > product.stock) {
    return res.status(400).json({ code: 1, message: `库存不足，仅剩 ${product.stock} 件` });
  }

  const carts = getCarts();
  const exist = carts.find(c => c.userId === req.user.id && c.productId === parseInt(productId));

  if (exist) {
    const newQty = exist.quantity + qty;
    if (newQty > product.stock) {
      return res.status(400).json({ code: 1, message: `库存不足，购物车已有 ${exist.quantity} 件` });
    }
    exist.quantity = newQty;
  } else {
    carts.push({
      id: generateId(),
      userId: req.user.id,
      productId: parseInt(productId),
      quantity: qty,
    });
  }

  saveCarts();

  // 返回更新后的购物车
  const myCart = carts
    .filter(c => c.userId === req.user.id)
    .map(c => {
      const p = products.find(p => p.id === c.productId);
      return {
        ...c,
        productName: p ? p.name : '',
        productImage: p ? p.image : '',
        productPrice: p ? p.price : 0,
        productStock: p ? p.stock : 0,
      };
    });

  res.status(201).json({ code: 0, data: myCart });
});

// PUT /api/cart/:id - 修改购物车数量
app.put('/api/cart/:id', auth, (req, res) => {
  const { quantity } = req.body;
  const qty = parseInt(quantity);

  if (!qty || qty < 1) {
    return res.status(400).json({ code: 1, message: '数量至少为1' });
  }

  const carts = getCarts();
  const item = carts.find(c => c.id === req.params.id && c.userId === req.user.id);
  if (!item) {
    return res.status(404).json({ code: 1, message: '购物车项不存在' });
  }

  const products = getProducts();
  const product = products.find(p => p.id === item.productId);
  if (product && qty > product.stock) {
    return res.status(400).json({ code: 1, message: `库存不足，仅剩 ${product.stock} 件` });
  }

  item.quantity = qty;
  saveCarts();
  res.json({ code: 0, data: item });
});

// DELETE /api/cart/:id - 删除购物车项
app.delete('/api/cart/:id', auth, (req, res) => {
  const carts = getCarts();
  const index = carts.findIndex(c => c.id === req.params.id && c.userId === req.user.id);
  if (index === -1) {
    return res.status(404).json({ code: 1, message: '购物车项不存在' });
  }
  carts.splice(index, 1);
  saveCarts();
  res.json({ code: 0, message: '已移除' });
});

// ==================== 订单模块（需登录）====================

// GET /api/orders - 获取我的订单
app.get('/api/orders', auth, (req, res) => {
  const orders = getOrders();
  const myOrders = orders
    .filter(o => o.userId === req.user.id)
    .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));

  res.json({ code: 0, data: myOrders });
});

// POST /api/orders - 结算下单（清空购物车）
app.post('/api/orders', auth, (req, res) => {
  const carts = getCarts();
  const products = getProducts();

  const myCart = carts.filter(c => c.userId === req.user.id);
  if (myCart.length === 0) {
    return res.status(400).json({ code: 1, message: '购物车为空，无法下单' });
  }

  // 构建订单项，校验库存
  const items = [];
  let totalAmount = 0;
  for (const cartItem of myCart) {
    const product = products.find(p => p.id === cartItem.productId);
    if (!product) continue;
    if (cartItem.quantity > product.stock) {
      return res.status(400).json({
        code: 1,
        message: `「${product.name}」库存不足，仅剩 ${product.stock} 件`,
      });
    }
    items.push({
      productId: product.id,
      name: product.name,
      price: product.price,
      quantity: cartItem.quantity,
    });
    totalAmount += product.price * cartItem.quantity;

    // 扣减库存
    product.stock -= cartItem.quantity;
  }

  // 生成订单
  const order = {
    id: generateId(),
    userId: req.user.id,
    items,
    totalAmount: Math.round(totalAmount * 100) / 100,
    status: 'pending',
    createdAt: new Date().toISOString(),
  };

  const orders = getOrders();
  orders.push(order);
  saveOrders();

  // 更新库存 & 清空购物车
  trySave(PRODUCTS_FILE, products);
  _carts = _carts.filter(c => c.userId !== req.user.id);
  saveCarts();

  res.status(201).json({ code: 0, data: order });
});

// PUT /api/orders/:id - 更新订单状态
app.put('/api/orders/:id', auth, (req, res) => {
  const { status } = req.body;
  const validStatuses = ['pending', 'paid', 'shipped', 'delivered'];
  if (!validStatuses.includes(status)) {
    return res.status(400).json({ code: 1, message: '无效的订单状态' });
  }

  const orders = getOrders();
  const order = orders.find(o => o.id === req.params.id && o.userId === req.user.id);
  if (!order) {
    return res.status(404).json({ code: 1, message: '订单不存在' });
  }

  // 状态流转校验
  const orderIndex = validStatuses.indexOf(order.status);
  const targetIndex = validStatuses.indexOf(status);
  if (targetIndex <= orderIndex && !(order.status === 'pending' && status === 'pending')) {
    return res.status(400).json({ code: 1, message: `无法从「${order.status}」变更为「${status}」` });
  }

  order.status = status;
  saveOrders();
  res.json({ code: 0, data: order });
});

// ==================== 启动 ====================
app.listen(PORT, () => {
  console.log(`✅ 电商管理系统已启动: http://localhost:${PORT}`);
});
