# 模拟微服务：Thrift IDL 与服务定义

> 3 个互相调用的直播业务微服务的 Thrift IDL 定义，用于 PoC 验证。

---

## 1. 服务间调用关系

```
┌─────────────────┐     RPC      ┌─────────────────┐     RPC      ┌─────────────────┐
│  user-service   │─────────────→│  gift-service   │─────────────→│ payment-service │
│                 │              │                 │              │                 │
│ GetUserProfile  │              │ SendGift        │              │ Deduct          │
│ UpdateUser      │              │ GetGiftHistory  │              │ GetBalance      │
└────────┬────────┘              └────────┬────────┘              └────────┬────────┘
         │                                │                                │
         ▼                                ▼                                ▼
    [MySQL: users]                [MySQL: gift_records]            [MySQL: wallets]
```

**调用链示例**：
- 用户送礼物：`user-service.GetUserProfile` → `gift-service.SendGift` → `payment-service.Deduct`
- `user_id` 和 `phone_number` 贯穿整个调用链

---

## 2. 目录结构

```
mock-services/
├── idl/
│   ├── user.thrift          # 用户服务 IDL
│   ├── gift.thrift          # 礼物服务 IDL
│   └── payment.thrift       # 支付服务 IDL
│
├── user-service/
│   ├── handler.go           # Kitex handler 实现
│   ├── dal/
│   │   └── user.go          # 数据访问层（GORM）
│   └── main.go
│
├── gift-service/
│   ├── handler.go
│   ├── dal/
│   │   └── gift.go
│   └── main.go
│
└── payment-service/
    ├── handler.go
    ├── dal/
    │   └── wallet.go
    └── main.go
```

---

## 3. Thrift IDL 文件

### 3.1 user.thrift — 用户服务

```thrift
namespace go user.service

// 用户基本信息
struct User {
    1: required i64 user_id         // 用户唯一标识 ID
    2: required string nickname     // 用户昵称（公开显示名）
    3: required string phone_number // 用户手机号（PII，11位）
    4: optional string avatar_url   // 头像 URL
    5: required i32 level           // 用户等级（1-100）
    6: required bool is_anchor      // 是否为主播
    7: optional string id_card      // 身份证号（PII，仅实名认证后有值）
    8: required i64 created_at      // 注册时间（Unix 时间戳）
}

// 查询用户资料请求
struct GetUserProfileRequest {
    1: required i64 user_id         // 要查询的用户 ID
}

// 查询用户资料响应
struct GetUserProfileResponse {
    1: required i32 code            // 错误码，0 表示成功
    2: optional string message      // 错误信息
    3: optional User user           // 用户信息
}

// 更新用户信息请求
struct UpdateUserRequest {
    1: required i64 user_id         // 要更新的用户 ID
    2: optional string nickname     // 新昵称
    3: optional string phone_number // 新手机号（PII）
    4: optional string avatar_url   // 新头像 URL
}

// 更新用户信息响应
struct UpdateUserResponse {
    1: required i32 code            // 错误码
    2: optional string message      // 错误信息
}

// 用户服务接口
service UserService {
    // 获取用户详细资料
    GetUserProfileResponse GetUserProfile(1: GetUserProfileRequest req)
    
    // 更新用户基本信息
    UpdateUserResponse UpdateUser(1: UpdateUserRequest req)
}
```

### 3.2 gift.thrift — 礼物服务

```thrift
namespace go gift.service

// 礼物记录
struct GiftRecord {
    1: required i64 record_id       // 礼物记录唯一 ID
    2: required i64 sender_id       // 送礼者用户 ID
    3: required string sender_name  // 送礼者昵称（冗余，用于展示）
    4: required i64 receiver_id     // 收礼者（主播）用户 ID
    5: required i64 room_id         // 直播间 ID
    6: required i32 gift_id         // 礼物类型 ID（1=玫瑰, 2=火箭, 3=城堡...）
    7: required i32 gift_count      // 礼物数量
    8: required i64 gift_value      // 礼物总价值（单位：分）
    9: required i64 created_at      // 送礼时间（Unix 时间戳）
}

// 送礼物请求
struct SendGiftRequest {
    1: required i64 sender_id       // 送礼者用户 ID
    2: required i64 receiver_id     // 收礼主播 ID
    3: required i64 room_id         // 直播间 ID
    4: required i32 gift_id         // 礼物类型 ID
    5: required i32 gift_count      // 数量（1-99）
    6: required i64 gift_price      // 单价（分），客户端传入用于校验
}

// 送礼物响应
struct SendGiftResponse {
    1: required i32 code            // 错误码，0=成功, 1001=余额不足, 1002=直播间不存在
    2: optional string message      // 错误信息
    3: optional i64 record_id       // 礼物记录 ID
    4: optional i64 remaining_balance // 送礼后剩余余额（分）
}

// 查询礼物历史请求
struct GetGiftHistoryRequest {
    1: required i64 user_id         // 用户 ID（查自己的送礼/收礼记录）
    2: required string role         // "sender" 或 "receiver"
    3: optional i32 page_size       // 分页大小（默认 20）
    4: optional i64 cursor          // 分页游标
}

// 查询礼物历史响应
struct GetGiftHistoryResponse {
    1: required i32 code            // 错误码
    2: optional string message      // 错误信息
    3: optional list<GiftRecord> records  // 礼物记录列表
    4: optional i64 next_cursor     // 下一页游标
    5: optional bool has_more       // 是否还有更多
}

// 礼物服务接口
service GiftService {
    // 送礼物（会调用 payment-service 扣款）
    SendGiftResponse SendGift(1: SendGiftRequest req)
    
    // 查询礼物历史记录
    GetGiftHistoryResponse GetGiftHistory(1: GetGiftHistoryRequest req)
}
```

### 3.3 payment.thrift — 支付服务

```thrift
namespace go payment.service

// 钱包信息
struct Wallet {
    1: required i64 user_id         // 用户 ID
    2: required i64 balance         // 余额（分）—— 金融敏感数据
    3: required i64 total_income    // 累计收入（分）—— 金融敏感数据
    4: required i64 total_expense   // 累计支出（分）—— 金融敏感数据
    5: required i64 updated_at      // 最后更新时间
}

// 扣款请求
struct DeductRequest {
    1: required i64 user_id         // 被扣款的用户 ID
    2: required i64 amount          // 扣款金额（分）
    3: required string reason       // 扣款原因（如 "send_gift"）
    4: optional string idempotent_key // 幂等键（防止重复扣款）
}

// 扣款响应
struct DeductResponse {
    1: required i32 code            // 错误码，0=成功, 2001=余额不足, 2002=重复请求
    2: optional string message      // 错误信息
    3: optional i64 remaining_balance // 扣款后剩余余额（分）—— 金融敏感
}

// 查询余额请求
struct GetBalanceRequest {
    1: required i64 user_id         // 用户 ID
}

// 查询余额响应
struct GetBalanceResponse {
    1: required i32 code            // 错误码
    2: optional string message      // 错误信息
    3: optional Wallet wallet       // 钱包信息
}

// 支付服务接口
service PaymentService {
    // 扣减用户余额（由 gift-service 调用）
    DeductResponse Deduct(1: DeductRequest req)
    
    // 查询用户余额
    GetBalanceResponse GetBalance(1: GetBalanceRequest req)
}
```

---

## 4. 敏感字段清单

用于 PoC 验证时对比 LLM 提取结果：

| 服务 | 字段 | 敏感性 | 说明 |
|------|------|--------|------|
| user-service | `User.phone_number` | **PII** | 手机号 |
| user-service | `User.id_card` | **PII** | 身份证号 |
| user-service | `UpdateUserRequest.phone_number` | **PII** | 新手机号 |
| payment-service | `Wallet.balance` | **Financial** | 余额 |
| payment-service | `Wallet.total_income` | **Financial** | 累计收入 |
| payment-service | `Wallet.total_expense` | **Financial** | 累计支出 |
| payment-service | `DeductRequest.amount` | **Financial** | 扣款金额 |
| payment-service | `DeductResponse.remaining_balance` | **Financial** | 剩余余额 |
| gift-service | `GiftRecord.gift_value` | **Financial** | 礼物价值 |
| gift-service | `SendGiftRequest.gift_price` | **Financial** | 礼物单价 |
| gift-service | `SendGiftResponse.remaining_balance` | **Financial** | 剩余余额 |

**Ground Truth**：共 11 个敏感字段（4 PII + 7 Financial），用于评估 LLM 提取精度。

---

## 5. 字段传播链（Ground Truth）

```
sender_id 传播链:
  SendGiftRequest.sender_id → GiftRecord.sender_id → gift_records.sender_id
  SendGiftRequest.sender_id → DeductRequest.user_id → wallets.user_id (WHERE)

phone_number 传播链:
  GetUserProfileResponse.user.phone_number ← User.phone_number ← users.phone_number
  UpdateUserRequest.phone_number → users.phone_number (UPDATE)

balance 传播链:
  DeductResponse.remaining_balance ← Wallet.balance ← wallets.balance
  GetBalanceResponse.wallet.balance ← Wallet.balance ← wallets.balance
  SendGiftResponse.remaining_balance ← DeductResponse.remaining_balance
```

---

*最后更新: 2026-03-05*
