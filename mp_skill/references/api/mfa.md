## mfa

- `POST /api/v1/mfa/otp/disable` — 关闭当前用户的 OTP 验证
- `POST /api/v1/mfa/otp/generate` — 生成 OTP 验证 URI
- `POST /api/v1/mfa/otp/verify` — 绑定并验证 OTP
- `POST /api/v1/mfa/passkey/delete` — 删除 PassKey
- `GET /api/v1/mfa/passkey/list` — 获取当前用户的 PassKey 列表
- `POST /api/v1/mfa/passkey/register/finish` — 完成注册 PassKey
- `POST /api/v1/mfa/passkey/register/start` — 开始注册 PassKey
- `POST /api/v1/mfa/passkey/verify` — PassKey 二次验证
