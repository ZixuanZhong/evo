# 模拟微服务：Kitex Handler 实现 + DB Schema

> 基于 IDL 定义，3 个服务的完整 Go handler 实现、GORM 数据访问层和 MySQL schema。

---

## 1. MySQL Schema

### 1.1 users 表（user-service）

```sql
CREATE TABLE `users` (
    `id`           BIGINT       NOT NULL AUTO_INCREMENT COMMENT '用户唯一标识 ID',
    `nickname`     VARCHAR(64)  NOT NULL DEFAULT '' COMMENT '用户昵称（公开显示名）',
    `phone_number` VARCHAR(20)  NOT NULL DEFAULT '' COMMENT '用户手机号（PII，11位）',
    `avatar_url`   VARCHAR(512) DEFAULT '' COMMENT '头像 URL',
    `level`        INT          NOT NULL DEFAULT 1 COMMENT '用户等级（1-100）',
    `is_anchor`    TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '是否为主播（0否1是）',
    `id_card`      VARCHAR(20)  DEFAULT NULL COMMENT '身份证号（PII，仅实名认证后有值）',
    `created_at`   BIGINT       NOT NULL COMMENT '注册时间（Unix 时间戳）',
    `updated_at`   BIGINT       NOT NULL COMMENT '最后更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_phone` (`phone_number`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户信息表';
```

### 1.2 gift_records 表（gift-service）

```sql
CREATE TABLE `gift_records` (
    `id`            BIGINT       NOT NULL AUTO_INCREMENT COMMENT '礼物记录唯一 ID',
    `sender_id`     BIGINT       NOT NULL COMMENT '送礼者用户 ID',
    `sender_name`   VARCHAR(64)  NOT NULL DEFAULT '' COMMENT '送礼者昵称（冗余展示）',
    `receiver_id`   BIGINT       NOT NULL COMMENT '收礼者（主播）用户 ID',
    `room_id`       BIGINT       NOT NULL COMMENT '直播间 ID',
    `gift_id`       INT          NOT NULL COMMENT '礼物类型 ID',
    `gift_count`    INT          NOT NULL DEFAULT 1 COMMENT '礼物数量',
    `gift_value`    BIGINT       NOT NULL COMMENT '礼物总价值（单位：分）',
    `created_at`    BIGINT       NOT NULL COMMENT '送礼时间（Unix 时间戳）',
    PRIMARY KEY (`id`),
    KEY `idx_sender` (`sender_id`, `created_at`),
    KEY `idx_receiver` (`receiver_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='礼物记录表';
```

### 1.3 wallets 表（payment-service）

```sql
CREATE TABLE `wallets` (
    `user_id`       BIGINT       NOT NULL COMMENT '用户 ID',
    `balance`       BIGINT       NOT NULL DEFAULT 0 COMMENT '余额（分）—— 金融敏感',
    `total_income`  BIGINT       NOT NULL DEFAULT 0 COMMENT '累计收入（分）',
    `total_expense` BIGINT       NOT NULL DEFAULT 0 COMMENT '累计支出（分）',
    `updated_at`    BIGINT       NOT NULL COMMENT '最后更新时间',
    PRIMARY KEY (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户钱包表';
```

---

## 2. user-service 实现

### 2.1 dal/user.go — 数据访问层

```go
package dal

import (
    "context"
    "gorm.io/gorm"
)

// UserModel 用户表的 GORM 模型
// 映射到 MySQL users 表
type UserModel struct {
    ID          int64  `gorm:"column:id;primaryKey;autoIncrement"`
    Nickname    string `gorm:"column:nickname"`
    PhoneNumber string `gorm:"column:phone_number"` // PII: 用户手机号
    AvatarURL   string `gorm:"column:avatar_url"`
    Level       int32  `gorm:"column:level"`
    IsAnchor    bool   `gorm:"column:is_anchor"`
    IDCard      string `gorm:"column:id_card"`      // PII: 身份证号
    CreatedAt   int64  `gorm:"column:created_at"`
    UpdatedAt   int64  `gorm:"column:updated_at"`
}

func (UserModel) TableName() string { return "users" }

// GetUserByID 根据用户 ID 查询用户信息
// 读取 users 表所有字段，包含 phone_number（PII）
func GetUserByID(ctx context.Context, db *gorm.DB, userID int64) (*UserModel, error) {
    var user UserModel
    err := db.WithContext(ctx).Where("id = ?", userID).First(&user).Error
    if err != nil {
        return nil, err
    }
    return &user, nil
}

// UpdateUser 更新用户基本信息
// 可能更新 phone_number（PII）
func UpdateUser(ctx context.Context, db *gorm.DB, userID int64, updates map[string]interface{}) error {
    return db.WithContext(ctx).Model(&UserModel{}).
        Where("id = ?", userID).
        Updates(updates).Error
}
```

### 2.2 handler.go — Kitex Handler

```go
package main

import (
    "context"
    "time"
    "user-service/dal"
    user "user-service/kitex_gen/user/service"
)

// UserServiceImpl 实现 UserService 接口
type UserServiceImpl struct {
    db *gorm.DB
}

// GetUserProfile 获取用户详细资料
// 从 DB 读取用户信息，包含 phone_number（PII）和 id_card（PII）
func (s *UserServiceImpl) GetUserProfile(ctx context.Context, req *user.GetUserProfileRequest) (*user.GetUserProfileResponse, error) {
    // 根据 user_id 查询 DB
    userModel, err := dal.GetUserByID(ctx, s.db, req.UserId)
    if err != nil {
        return &user.GetUserProfileResponse{
            Code:    500,
            Message: strPtr("用户不存在"),
        }, nil
    }

    // 将 DB 模型转换为 Thrift 响应
    // 注意：phone_number 和 id_card 直接返回（PII 暴露风险点）
    return &user.GetUserProfileResponse{
        Code: 0,
        User: &user.User{
            UserId:      userModel.ID,           // 用户 ID
            Nickname:    userModel.Nickname,      // 昵称
            PhoneNumber: userModel.PhoneNumber,   // PII: 手机号直接返回！
            AvatarUrl:   &userModel.AvatarURL,    // 头像
            Level:       int32(userModel.Level),   // 等级
            IsAnchor:    userModel.IsAnchor,       // 是否主播
            IdCard:      &userModel.IDCard,        // PII: 身份证号直接返回！
            CreatedAt:   userModel.CreatedAt,      // 注册时间
        },
    }, nil
}

// UpdateUser 更新用户基本信息
// 可能写入新的 phone_number（PII）到 DB
func (s *UserServiceImpl) UpdateUser(ctx context.Context, req *user.UpdateUserRequest) (*user.UpdateUserResponse, error) {
    updates := make(map[string]interface{})

    // 收集需要更新的字段
    if req.Nickname != nil {
        updates["nickname"] = *req.Nickname
    }
    if req.PhoneNumber != nil {
        // PII 字段写入 DB
        updates["phone_number"] = *req.PhoneNumber
    }
    if req.AvatarUrl != nil {
        updates["avatar_url"] = *req.AvatarUrl
    }
    updates["updated_at"] = time.Now().Unix()

    err := dal.UpdateUser(ctx, s.db, req.UserId, updates)
    if err != nil {
        return &user.UpdateUserResponse{Code: 500, Message: strPtr("更新失败")}, nil
    }
    return &user.UpdateUserResponse{Code: 0, Message: strPtr("success")}, nil
}
```

---

## 3. gift-service 实现

### 3.1 dal/gift.go — 数据访问层

```go
package dal

import (
    "context"
    "gorm.io/gorm"
)

// GiftRecordModel 礼物记录表的 GORM 模型
type GiftRecordModel struct {
    ID         int64  `gorm:"column:id;primaryKey;autoIncrement"`
    SenderID   int64  `gorm:"column:sender_id"`    // 送礼者用户 ID
    SenderName string `gorm:"column:sender_name"`  // 送礼者昵称
    ReceiverID int64  `gorm:"column:receiver_id"`  // 收礼主播 ID
    RoomID     int64  `gorm:"column:room_id"`      // 直播间 ID
    GiftID     int32  `gorm:"column:gift_id"`      // 礼物类型
    GiftCount  int32  `gorm:"column:gift_count"`   // 数量
    GiftValue  int64  `gorm:"column:gift_value"`   // 总价值（分）—— Financial
    CreatedAt  int64  `gorm:"column:created_at"`
}

func (GiftRecordModel) TableName() string { return "gift_records" }

// InsertGiftRecord 插入一条礼物记录
// 写入 sender_id, receiver_id, gift_value 等字段
func InsertGiftRecord(ctx context.Context, db *gorm.DB, record *GiftRecordModel) (int64, error) {
    err := db.WithContext(ctx).Create(record).Error
    return record.ID, err
}

// GetGiftsBySender 查询某用户送出的礼物记录
func GetGiftsBySender(ctx context.Context, db *gorm.DB, senderID int64, limit int, cursor int64) ([]*GiftRecordModel, error) {
    var records []*GiftRecordModel
    query := db.WithContext(ctx).Where("sender_id = ?", senderID)
    if cursor > 0 {
        query = query.Where("id < ?", cursor)
    }
    err := query.Order("id DESC").Limit(limit).Find(&records).Error
    return records, err
}

// GetGiftsByReceiver 查询某主播收到的礼物记录
func GetGiftsByReceiver(ctx context.Context, db *gorm.DB, receiverID int64, limit int, cursor int64) ([]*GiftRecordModel, error) {
    var records []*GiftRecordModel
    query := db.WithContext(ctx).Where("receiver_id = ?", receiverID)
    if cursor > 0 {
        query = query.Where("id < ?", cursor)
    }
    err := query.Order("id DESC").Limit(limit).Find(&records).Error
    return records, err
}
```

### 3.2 handler.go — Kitex Handler

```go
package main

import (
    "context"
    "time"
    "gift-service/dal"
    gift "gift-service/kitex_gen/gift/service"
    payment "gift-service/kitex_gen/payment/service"
)

// GiftServiceImpl 实现 GiftService 接口
type GiftServiceImpl struct {
    db            *gorm.DB
    paymentClient payment.Client // 支付服务 RPC 客户端
    userClient    user.Client    // 用户服务 RPC 客户端
}

// SendGift 送礼物
// 调用链：gift-service.SendGift → payment-service.Deduct
// 字段传播：req.SenderID → DeductRequest.UserID → wallets.user_id
func (s *GiftServiceImpl) SendGift(ctx context.Context, req *gift.SendGiftRequest) (*gift.SendGiftResponse, error) {
    // 计算礼物总价值
    totalValue := int64(req.GiftCount) * req.GiftPrice

    // 1. 调用支付服务扣款
    // 字段传播：sender_id → user_id（语义：送礼者是被扣款的人）
    deductResp, err := s.paymentClient.Deduct(ctx, &payment.DeductRequest{
        UserId: req.SenderId,              // sender_id 传播为 user_id
        Amount: totalValue,                // gift_price * count → amount
        Reason: "send_gift",               // 扣款原因
    })
    if err != nil {
        return &gift.SendGiftResponse{Code: 500, Message: strPtr("扣款服务异常")}, nil
    }
    if deductResp.Code != 0 {
        return &gift.SendGiftResponse{
            Code:    1001,
            Message: deductResp.Message,
        }, nil
    }

    // 2. 查询送礼者昵称（用于冗余存储）
    userResp, _ := s.userClient.GetUserProfile(ctx, &user.GetUserProfileRequest{
        UserId: req.SenderId,
    })
    senderName := ""
    if userResp != nil && userResp.User != nil {
        senderName = userResp.User.Nickname
    }

    // 3. 写入礼物记录到 DB
    // 字段传播：req 的多个字段 → GiftRecordModel → gift_records 表
    recordID, err := dal.InsertGiftRecord(ctx, s.db, &dal.GiftRecordModel{
        SenderID:   req.SenderId,        // sender_id 直传
        SenderName: senderName,           // 从 user-service 获取
        ReceiverID: req.ReceiverId,      // receiver_id 直传
        RoomID:     req.RoomId,          // room_id 直传
        GiftID:     req.GiftId,          // gift_id 直传
        GiftCount:  req.GiftCount,       // gift_count 直传
        GiftValue:  totalValue,          // gift_price × count → gift_value（transform）
        CreatedAt:  time.Now().Unix(),
    })
    if err != nil {
        return &gift.SendGiftResponse{Code: 500, Message: strPtr("记录写入失败")}, nil
    }

    return &gift.SendGiftResponse{
        Code:             0,
        RecordId:         &recordID,
        RemainingBalance: deductResp.RemainingBalance, // 余额从 payment-service 透传
    }, nil
}

// GetGiftHistory 查询礼物历史
func (s *GiftServiceImpl) GetGiftHistory(ctx context.Context, req *gift.GetGiftHistoryRequest) (*gift.GetGiftHistoryResponse, error) {
    pageSize := int(req.GetPageSize())
    if pageSize <= 0 {
        pageSize = 20
    }
    cursor := req.GetCursor()

    var records []*dal.GiftRecordModel
    var err error
    if req.Role == "sender" {
        records, err = dal.GetGiftsBySender(ctx, s.db, req.UserId, pageSize+1, cursor)
    } else {
        records, err = dal.GetGiftsByReceiver(ctx, s.db, req.UserId, pageSize+1, cursor)
    }
    if err != nil {
        return &gift.GetGiftHistoryResponse{Code: 500, Message: strPtr("查询失败")}, nil
    }

    hasMore := len(records) > pageSize
    if hasMore {
        records = records[:pageSize]
    }

    // 转换为 Thrift 响应
    var thriftRecords []*gift.GiftRecord
    for _, r := range records {
        thriftRecords = append(thriftRecords, &gift.GiftRecord{
            RecordId:   r.ID,
            SenderId:   r.SenderID,
            SenderName: r.SenderName,
            ReceiverId: r.ReceiverID,
            RoomId:     r.RoomID,
            GiftId:     r.GiftID,
            GiftCount:  r.GiftCount,
            GiftValue:  r.GiftValue,     // Financial 数据从 DB 返回
            CreatedAt:  r.CreatedAt,
        })
    }

    var nextCursor *int64
    if hasMore && len(records) > 0 {
        nc := records[len(records)-1].ID
        nextCursor = &nc
    }

    return &gift.GetGiftHistoryResponse{
        Code:       0,
        Records:    thriftRecords,
        NextCursor: nextCursor,
        HasMore:    &hasMore,
    }, nil
}
```

---

## 4. payment-service 实现

### 4.1 dal/wallet.go — 数据访问层

```go
package dal

import (
    "context"
    "gorm.io/gorm"
)

// WalletModel 钱包表的 GORM 模型
type WalletModel struct {
    UserID       int64 `gorm:"column:user_id;primaryKey"` // 用户 ID
    Balance      int64 `gorm:"column:balance"`            // 余额（分）—— Financial
    TotalIncome  int64 `gorm:"column:total_income"`       // 累计收入 —— Financial
    TotalExpense int64 `gorm:"column:total_expense"`      // 累计支出 —— Financial
    UpdatedAt    int64 `gorm:"column:updated_at"`
}

func (WalletModel) TableName() string { return "wallets" }

// GetWalletByUserID 查询用户钱包
// 读取 wallets 表，返回 balance 等金融敏感数据
func GetWalletByUserID(ctx context.Context, db *gorm.DB, userID int64) (*WalletModel, error) {
    var wallet WalletModel
    err := db.WithContext(ctx).Where("user_id = ?", userID).First(&wallet).Error
    return &wallet, err
}

// DeductBalance 扣减用户余额
// 更新 wallets.balance（金融敏感操作）
func DeductBalance(ctx context.Context, db *gorm.DB, userID int64, amount int64) (int64, error) {
    var wallet WalletModel

    // 使用事务保证原子性
    err := db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
        // 加行锁查询当前余额
        if err := tx.Set("gorm:query_option", "FOR UPDATE").
            Where("user_id = ?", userID).First(&wallet).Error; err != nil {
            return err
        }

        // 检查余额是否充足
        if wallet.Balance < amount {
            return fmt.Errorf("insufficient balance")
        }

        // 扣减余额，增加累计支出
        return tx.Model(&WalletModel{}).Where("user_id = ?", userID).Updates(map[string]interface{}{
            "balance":       gorm.Expr("balance - ?", amount),
            "total_expense": gorm.Expr("total_expense + ?", amount),
            "updated_at":    time.Now().Unix(),
        }).Error
    })

    if err != nil {
        return 0, err
    }
    return wallet.Balance - amount, nil // 返回扣款后余额
}
```

### 4.2 handler.go — Kitex Handler

```go
package main

import (
    "context"
    "payment-service/dal"
    payment "payment-service/kitex_gen/payment/service"
)

// PaymentServiceImpl 实现 PaymentService 接口
type PaymentServiceImpl struct {
    db *gorm.DB
}

// Deduct 扣减用户余额
// 由 gift-service 调用，字段传播：DeductRequest.user_id → wallets.user_id
func (s *PaymentServiceImpl) Deduct(ctx context.Context, req *payment.DeductRequest) (*payment.DeductResponse, error) {
    // 扣减余额
    // 字段传播：req.UserId → WHERE wallets.user_id = ?
    // 字段传播：req.Amount → wallets.balance -= amount
    remainingBalance, err := dal.DeductBalance(ctx, s.db, req.UserId, req.Amount)
    if err != nil {
        if err.Error() == "insufficient balance" {
            return &payment.DeductResponse{
                Code:    2001,
                Message: strPtr("余额不足"),
            }, nil
        }
        return &payment.DeductResponse{Code: 500, Message: strPtr("扣款失败")}, nil
    }

    return &payment.DeductResponse{
        Code:             0,
        Message:          strPtr("success"),
        RemainingBalance: &remainingBalance, // Financial: 返回剩余余额
    }, nil
}

// GetBalance 查询用户余额
// 从 DB 读取钱包信息，包含 balance/total_income/total_expense（Financial）
func (s *PaymentServiceImpl) GetBalance(ctx context.Context, req *payment.GetBalanceRequest) (*payment.GetBalanceResponse, error) {
    wallet, err := dal.GetWalletByUserID(ctx, s.db, req.UserId)
    if err != nil {
        return &payment.GetBalanceResponse{Code: 500, Message: strPtr("查询失败")}, nil
    }

    return &payment.GetBalanceResponse{
        Code: 0,
        Wallet: &payment.Wallet{
            UserId:       wallet.UserID,
            Balance:      wallet.Balance,       // Financial: 余额
            TotalIncome:  wallet.TotalIncome,   // Financial: 累计收入
            TotalExpense: wallet.TotalExpense,   // Financial: 累计支出
            UpdatedAt:    wallet.UpdatedAt,
        },
    }, nil
}
```

---

## 5. 字段传播验证清单

用于对比传播算法 PoC 的输出：

| 起点 | 路径 | 终点 | 传播类型 |
|------|------|------|---------|
| `SendGiftReq.sender_id` | → `DeductReq.user_id` | `wallets.user_id` (WHERE) | pass_through + 改名 |
| `SendGiftReq.sender_id` | → `GiftRecordModel.SenderID` | `gift_records.sender_id` | pass_through |
| `SendGiftReq.gift_price` | × `gift_count` → `GiftRecordModel.GiftValue` | `gift_records.gift_value` | transform |
| `SendGiftReq.gift_price` | × `gift_count` → `DeductReq.Amount` | `wallets.balance` (UPDATE) | transform |
| `DeductResp.remaining_balance` | → `SendGiftResp.remaining_balance` | (API 响应) | pass_through |
| `WalletModel.Balance` | → `DeductResp.remaining_balance` | (API 响应链) | pass_through |
| `UserModel.PhoneNumber` | → `GetUserProfileResp.User.PhoneNumber` | (API 响应) | pass_through |

---

*最后更新: 2026-03-05*
