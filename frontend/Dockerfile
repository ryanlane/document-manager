FROM node:18-alpine

WORKDIR /app

COPY package.json package-lock.json ./
# RUN npm install
RUN npm ci

COPY . .

CMD ["npm", "run", "dev", "--", "--host"]
