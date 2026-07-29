# Laravel Task API

这是用于 DevMind MVP 检索评估的脱敏 Laravel API 示例项目。

## 关键结构

- `app/Http/Controllers/AuthController.php`：登录和 Token 生成；
- `app/Http/Middleware/Authenticate.php`：Bearer Token 认证检查；
- `routes/api.php`：登录和受保护任务接口路由。

项目采用 Laravel Sanctum 风格的 Bearer Token 认证。该目录只保留演示逻辑，不包含真实数据库连接、密码或 Token。

