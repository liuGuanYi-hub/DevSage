# Laravel API 认证说明

## 认证方式

示例项目使用 Laravel Sanctum 管理 API Token。客户端登录成功后获得 Bearer Token，访问受保护接口时通过以下请求头发送：

```http
Authorization: Bearer <token>
```

## 登录流程

1. 客户端向 `/api/login` 发送账号和密码；
2. `AuthController@login` 校验用户凭据；
3. 校验成功后生成 Token 并返回；
4. 受保护路由经过 `auth:sanctum` 中间件；
5. 中间件从请求头提取 Token，并将已认证用户放入当前请求上下文。

## 代码来源

- 登录控制器：`sample-data/repositories/laravel-task-api/app/Http/Controllers/AuthController.php`；
- 认证中间件：`sample-data/repositories/laravel-task-api/app/Http/Middleware/Authenticate.php`；
- API 路由：`sample-data/repositories/laravel-task-api/routes/api.php`。

