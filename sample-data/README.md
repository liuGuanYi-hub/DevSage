# DevSage 脱敏样例数据

这里的数据全部是为阶段 0 构造的演示数据，不包含真实项目密码、Token、用户数据或第三方服务密钥。

## 数据范围

- `docs/`：技术故障、认证方式和知识写回规则；
- `repositories/springboot-demo/`：模拟 Spring Boot 项目的控制器、服务和配置；
- `repositories/laravel-task-api/`：模拟 Laravel API 项目的认证中间件、控制器和路由。

## 使用约定

评估问题中的 `expected_sources` 使用相对于 DevSage 根目录的路径。索引器需要保留这些路径，并在后续回答中返回来源和行号。

