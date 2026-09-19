# 电商后端容器化：Node + Express
FROM node:22-alpine

WORKDIR /app

# 先拷贝依赖清单，利用构建缓存
COPY package*.json ./
RUN npm install --no-audit --no-fund

# 拷贝源码与数据
COPY . .

EXPOSE 3000

CMD ["node", "server.js"]
