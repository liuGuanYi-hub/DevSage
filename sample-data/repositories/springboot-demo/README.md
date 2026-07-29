# Spring Boot Demo

这是用于 DevMind MVP 检索评估的脱敏 Spring Boot 示例项目。

## 项目结构

- `src/main/java/com/example/devsage/UserController.java`：用户接口入口；
- `src/main/java/com/example/devsage/UserService.java`：用户查询业务逻辑；
- `src/main/resources/application.yml`：服务端口和应用配置。

## 示例接口

```text
GET /api/users/{id}
```

控制器接收用户 ID，调用 `UserService.findUser`，返回一个简单的用户数据对象。

