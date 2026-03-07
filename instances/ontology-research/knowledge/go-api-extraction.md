# Go-Hertz/Kitex API 语义提取：LLM 能从代码提取什么？

> 本文深入分析 LLM 从字节跳动主力框架 Go-Hertz（HTTP）和 Go-Kitex（RPC）代码中提取 API 语义的能力，含实际代码示例和 prompt 设计。

---

## 1. Go-Hertz 的典型代码结构

### 1.1 Hertz 是什么

Hertz 是字节跳动 CloudWeGo 开源的高性能 Go HTTP 框架。和 Gin 类似但性能更好。

**核心模式**：IDL 定义 → `hz` 代码生成 → handler 实现业务逻辑。

**参考**: [github.com/cloudwego/hertz](https://github.com/cloudwego/hertz), [cloudwego.io/docs/hertz](https://www.cloudwego.io/docs/hertz/tutorials/example/)

### 1.2 Hertz Handler 典型结构

```go
// handler/live_room.go

// CreateRoom 创建直播间
// @router /api/v1/room [POST]
func CreateRoom(ctx context.Context, c *app.RequestContext) {
    var req CreateRoomReq
    err := c.BindAndValidate(&req)
    if err != nil {
        c.JSON(400, BaseResp{Code: 400, Msg: err.Error()})
        return
    }

    // 调用 RPC 服务
    room, err := rpc.RoomClient.CreateRoom(ctx, &room_service.CreateRoomRequest{
        AnchorID:  req.AnchorID,
        Title:     req.Title,
        Category:  req.Category,
    })
    if err != nil {
        c.JSON(500, BaseResp{Code: 500, Msg: "创建失败"})
        return
    }

    c.JSON(200, CreateRoomResp{
        BaseResp: BaseResp{Code: 0, Msg: "success"},
        RoomID:   room.RoomID,
    })
}

// 请求/响应 struct（可能在同文件或 model/ 目录）
type CreateRoomReq struct {
    AnchorID int64  `json:"anchor_id" vd:"$>0"`       // 主播 ID
    Title    string `json:"title" vd:"len($)>0"`       // 直播间标题
    Category int32  `json:"category"`                   // 直播分类 ID
}

type CreateRoomResp struct {
    BaseResp BaseResp `json:"base_resp"`
    RoomID   int64    `json:"room_id"`                  // 新创建的直播间 ID
}

type BaseResp struct {
    Code int32  `json:"code"`
    Msg  string `json:"msg"`
}
```

### 1.3 Hertz 代码的关键特征（LLM 提取线索）

| 特征 | 位置 | LLM 可提取性 |
|------|------|-------------|
| HTTP method + 路由 | `@router` 注释或路由注册代码 | ⭐⭐⭐⭐⭐ 模式固定 |
| 请求 struct + json tag | `type XXXReq struct` + `json:"xxx"` | ⭐⭐⭐⭐⭐ 显式定义 |
| 响应 struct + json tag | `type XXXResp struct` + `json:"xxx"` | ⭐⭐⭐⭐⭐ 显式定义 |
| 参数绑定 | `c.BindAndValidate(&req)` | ⭐⭐⭐⭐⭐ 固定模式 |
| 验证规则 | `vd:"$>0"` tag | ⭐⭐⭐⭐ tag 解析 |
| 下游 RPC 调用 | `rpc.XXXClient.Method(...)` | ⭐⭐⭐⭐ 需要识别 client 变量 |
| 字段语义 | 注释 + 命名 | ⭐⭐⭐⭐ 命名好时准确 |
| 错误处理逻辑 | if err 分支 | ⭐⭐⭐ 需要理解控制流 |

---

## 2. Go-Kitex 的典型代码结构

### 2.1 Kitex 是什么

Kitex 是字节 CloudWeGo 的高性能 Go RPC 框架，支持 Thrift 和 Protobuf。

**核心模式**：Thrift IDL 定义 → `kitex` 工具生成 → handler 实现业务逻辑。

**参考**: [github.com/cloudwego/kitex](https://github.com/cloudwego/kitex), [cloudwego.io/docs/kitex](https://www.cloudwego.io/docs/kitex/getting-started/)

### 2.2 Thrift IDL 示例

```thrift
// idl/room_service.thrift
namespace go room.service

struct CreateRoomRequest {
    1: required i64 anchor_id   // 主播 ID
    2: required string title    // 直播间标题
    3: optional i32 category    // 分类 ID
}

struct CreateRoomResponse {
    1: required i64 room_id     // 直播间 ID
    2: required string status   // 直播间状态
}

struct GetRoomRequest {
    1: required i64 room_id
}

struct GetRoomResponse {
    1: required i64 room_id
    2: required string title
    3: required i64 anchor_id
    4: required string anchor_name
    5: required i32 viewer_count
}

service RoomService {
    CreateRoomResponse CreateRoom(1: CreateRoomRequest req)
    GetRoomResponse GetRoom(1: GetRoomRequest req)
}
```

### 2.3 Kitex Handler 实现

```go
// handler.go
package main

import (
    "context"
    "example/kitex_gen/room/service"
    "example/dal"
)

// RoomServiceImpl implements the RoomService interface defined in IDL.
type RoomServiceImpl struct{}

// CreateRoom 创建直播间
func (s *RoomServiceImpl) CreateRoom(ctx context.Context, req *service.CreateRoomRequest) (*service.CreateRoomResponse, error) {
    // 写入数据库
    roomID, err := dal.InsertRoom(ctx, dal.Room{
        AnchorID: req.AnchorID,
        Title:    req.Title,
        Category: req.GetCategory(),
    })
    if err != nil {
        return nil, err
    }

    return &service.CreateRoomResponse{
        RoomID: roomID,
        Status: "created",
    }, nil
}

// GetRoom 查询直播间详情
func (s *RoomServiceImpl) GetRoom(ctx context.Context, req *service.GetRoomRequest) (*service.GetRoomResponse, error) {
    room, err := dal.GetRoomByID(ctx, req.RoomID)
    if err != nil {
        return nil, err
    }
    anchor, _ := dal.GetUserByID(ctx, room.AnchorID)

    return &service.GetRoomResponse{
        RoomID:      room.ID,
        Title:       room.Title,
        AnchorID:    room.AnchorID,
        AnchorName:  anchor.Nickname,
        ViewerCount: int32(room.ViewerCount),
    }, nil
}
```

### 2.4 Kitex 代码的关键特征

| 特征 | 位置 | LLM 可提取性 |
|------|------|-------------|
| IDL 接口定义 | `.thrift` 文件 | ⭐⭐⭐⭐⭐ 结构化、无歧义 |
| 请求/响应类型 | IDL struct → 生成的 Go struct | ⭐⭐⭐⭐⭐ 有明确 field ID |
| Handler 函数签名 | `func (s *Impl) Method(ctx, req) (resp, error)` | ⭐⭐⭐⭐⭐ 固定模式 |
| 字段映射 | `req.AnchorID` → `dal.Room{AnchorID: ...}` | ⭐⭐⭐⭐ 赋值语句可追踪 |
| DB 操作 | `dal.InsertRoom(...)`, `dal.GetRoomByID(...)` | ⭐⭐⭐⭐ 需识别 DAL 调用 |
| 字段注释 | IDL 中的 `// 主播 ID` | ⭐⭐⭐⭐⭐ 如果有注释就很准 |

---

## 3. 模拟直播场景的 Go 代码

### 3.1 Hertz HTTP API：礼物打赏

```go
// handler/gift.go

// SendGift 观众给主播送礼物
// @router /api/v1/gift/send [POST]
func SendGift(ctx context.Context, c *app.RequestContext) {
    var req SendGiftReq
    if err := c.BindAndValidate(&req); err != nil {
        c.JSON(400, BaseResp{Code: 400, Msg: err.Error()})
        return
    }

    // 扣减观众余额
    err := rpc.PaymentClient.Deduct(ctx, &payment.DeductRequest{
        UserID: req.SenderID,
        Amount: req.GiftPrice,
        Reason: "send_gift",
    })
    if err != nil {
        c.JSON(500, BaseResp{Code: 500, Msg: "余额不足"})
        return
    }

    // 记录礼物
    giftRecord, _ := rpc.GiftClient.RecordGift(ctx, &gift_service.RecordGiftRequest{
        SenderID:   req.SenderID,
        ReceiverID: req.AnchorID,
        RoomID:     req.RoomID,
        GiftID:     req.GiftID,
        GiftCount:  req.Count,
    })

    c.JSON(200, SendGiftResp{
        BaseResp: BaseResp{Code: 0, Msg: "success"},
        RecordID: giftRecord.RecordID,
        Balance:  giftRecord.RemainingBalance,
    })
}

type SendGiftReq struct {
    SenderID  int64 `json:"sender_id" vd:"$>0"`    // 送礼观众的用户 ID
    AnchorID  int64 `json:"anchor_id" vd:"$>0"`    // 接收礼物的主播 ID
    RoomID    int64 `json:"room_id" vd:"$>0"`      // 直播间 ID
    GiftID    int32 `json:"gift_id" vd:"$>0"`      // 礼物类型 ID
    Count     int32 `json:"count" vd:"$>0&&$<=99"`  // 礼物数量
    GiftPrice int64 `json:"gift_price"`             // 单价（分）
}

type SendGiftResp struct {
    BaseResp BaseResp `json:"base_resp"`
    RecordID int64    `json:"record_id"`     // 礼物记录 ID
    Balance  int64    `json:"balance"`       // 送礼后观众剩余余额（分）
}
```

### 3.2 Kitex RPC：用户查询服务

```go
// user_service handler.go

// GetUserProfile 获取用户详细资料
func (s *UserServiceImpl) GetUserProfile(ctx context.Context, req *user_service.GetUserProfileRequest) (*user_service.GetUserProfileResponse, error) {
    user, err := dal.GetUserByID(ctx, req.UserID)
    if err != nil {
        return nil, err
    }

    return &user_service.GetUserProfileResponse{
        UserID:      user.ID,
        Nickname:    user.Nickname,
        AvatarURL:   user.AvatarURL,
        PhoneNumber: user.PhoneNumber,  // PII!
        Level:       user.Level,
        IsAnchor:    user.IsAnchor,
        CreatedAt:   user.CreatedAt.Unix(),
    }, nil
}
```

---

## 4. LLM Prompt 设计：从代码到结构化 JSON

### 4.1 System Prompt

```
你是一个代码语义分析助手。你的任务是分析 Go 代码并提取 API 的结构化信息。

对于每个 API/RPC 方法，输出以下 JSON 格式：
{
  "api_name": "方法名",
  "framework": "hertz|kitex",
  "http_method": "GET|POST|PUT|DELETE（仅 Hertz）",
  "route": "HTTP 路由路径（仅 Hertz）",
  "request_schema": {
    "struct_name": "请求 struct 名称",
    "fields": [
      {
        "name": "字段名",
        "go_type": "Go 类型",
        "json_name": "JSON 序列化名",
        "semantic": "字段的业务含义（一句话中文描述）",
        "sensitivity": "none|pii|financial|internal_id",
        "required": true/false
      }
    ]
  },
  "response_schema": { /* 同上格式 */ },
  "downstream_calls": [
    {
      "service": "下游服务名",
      "method": "调用的方法",
      "field_mapping": {"本地字段": "下游字段"}
    }
  ]
}

规则：
1. semantic 字段必须用中文描述业务含义，不要只重复字段名
2. sensitivity 根据字段语义判断：手机号/身份证/银行卡 → pii；金额/余额 → financial；内部 ID → internal_id
3. 如果代码中有注释，优先使用注释内容作为 semantic
4. downstream_calls 通过分析 RPC 客户端调用来识别
```

### 4.2 Few-Shot Example

**输入代码**：
```go
// @router /api/v1/room [POST]
func CreateRoom(ctx context.Context, c *app.RequestContext) {
    var req CreateRoomReq
    c.BindAndValidate(&req)
    room, _ := rpc.RoomClient.CreateRoom(ctx, &room_service.CreateRoomRequest{
        AnchorID: req.AnchorID, Title: req.Title, Category: req.Category,
    })
    c.JSON(200, CreateRoomResp{RoomID: room.RoomID})
}

type CreateRoomReq struct {
    AnchorID int64  `json:"anchor_id" vd:"$>0"`
    Title    string `json:"title" vd:"len($)>0"`
    Category int32  `json:"category"`
}
type CreateRoomResp struct {
    BaseResp BaseResp `json:"base_resp"`
    RoomID   int64    `json:"room_id"`
}
```

**期望输出**：
```json
{
  "api_name": "CreateRoom",
  "framework": "hertz",
  "http_method": "POST",
  "route": "/api/v1/room",
  "request_schema": {
    "struct_name": "CreateRoomReq",
    "fields": [
      {
        "name": "AnchorID",
        "go_type": "int64",
        "json_name": "anchor_id",
        "semantic": "创建直播间的主播用户 ID",
        "sensitivity": "internal_id",
        "required": true
      },
      {
        "name": "Title",
        "go_type": "string",
        "json_name": "title",
        "semantic": "直播间标题，用户可见的显示名称",
        "sensitivity": "none",
        "required": true
      },
      {
        "name": "Category",
        "go_type": "int32",
        "json_name": "category",
        "semantic": "直播间分类 ID，如游戏、唱歌、聊天等",
        "sensitivity": "none",
        "required": false
      }
    ]
  },
  "response_schema": {
    "struct_name": "CreateRoomResp",
    "fields": [
      {
        "name": "RoomID",
        "go_type": "int64",
        "json_name": "room_id",
        "semantic": "新创建的直播间唯一标识 ID",
        "sensitivity": "internal_id",
        "required": true
      }
    ]
  },
  "downstream_calls": [
    {
      "service": "RoomService",
      "method": "CreateRoom",
      "field_mapping": {
        "AnchorID": "AnchorID",
        "Title": "Title",
        "Category": "Category"
      }
    }
  ]
}
```

### 4.3 Zero-Shot Prompt（简化版）

当不想用 few-shot 时，可以用更简洁的 prompt：

```
分析以下 Go 代码，提取 API 信息。输出 JSON 格式，包含：
api_name, framework(hertz/kitex), http_method, route, 
request_schema(字段名、类型、JSON名、中文语义、敏感性),
response_schema(同上),
downstream_calls(下游服务、方法、字段映射)。

每个字段的 semantic 必须用中文描述业务含义。
sensitivity 值：none/pii/financial/internal_id。

代码：
{code}
```

---

## 5. Prompt 设计关键点分析

### 5.1 Few-Shot vs Zero-Shot

| 策略 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| **Zero-Shot** | prompt 短、省 token | 输出格式不稳定、语义描述质量波动 | 大规模扫描（成本敏感） |
| **One-Shot** | 格式稳定、质量好 | 多消耗 ~500 token | 推荐的平衡选择 |
| **Few-Shot（2-3 例）** | 最高质量和一致性 | 消耗多、prompt 长 | 高精度场景（PII 检测） |

**推荐**：One-Shot（一个 Hertz 例子 + 一个 Kitex 例子），约增加 800 token，但格式一致性大幅提升。

### 5.2 结构化输出格式

**JSON 格式**是最佳选择：
- LLM（GPT-4/Claude）对 JSON 输出的遵循度很高
- 可以用 JSON Schema 做后处理验证
- 下游 pipeline 直接 `json.Unmarshal`

**技巧**：
- 在 prompt 中给出完整 JSON Schema 定义
- 使用 GPT-4 的 `response_format: {"type": "json_object"}` 或 Claude 的 structured output
- 对输出做 schema 校验，失败时自动重试

### 5.3 处理复杂嵌套 Struct

Hertz/Kitex 代码中经常有嵌套 struct：

```go
type CreateRoomResp struct {
    BaseResp BaseResp     `json:"base_resp"`  // 嵌套 struct
    Room     RoomDetail   `json:"room"`       // 又一层嵌套
}

type RoomDetail struct {
    ID       int64        `json:"id"`
    Anchor   AnchorBrief  `json:"anchor"`     // 第三层嵌套
}
```

**处理策略**：
1. **展平（推荐）**：让 LLM 递归展开所有嵌套 struct，输出扁平化的字段列表，每个字段用 `parent.child.field` 的路径表示
2. **保持层级**：输出嵌套 JSON，保留原始结构
3. **AST 预处理**：用 Go AST 工具先提取所有 struct 定义和类型引用，作为 prompt 的附加上下文

**推荐方案**：先用 Go AST 提取 struct 依赖关系，把被引用的 struct 定义一起注入 prompt。

### 5.4 处理 Thrift IDL vs Go Handler

对于 Kitex 服务，有两个信息来源：

| 来源 | 信息质量 | 适合提取 |
|------|---------|---------|
| **Thrift IDL** | 结构化、有字段编号、有注释 | 接口定义、字段类型、required/optional |
| **Go Handler** | 有业务逻辑、有字段映射 | 字段传递关系、下游调用、DB 操作 |

**最佳实践**：两者结合。先从 IDL 提取 schema（精确），再从 handler 提取字段映射和调用关系（需要 LLM 理解）。

---

## 6. 局限性与挑战

### 6.1 跨文件 Struct 定义 ⚠️

最大挑战：请求/响应 struct 可能定义在另一个文件：

```go
// handler.go
func CreateRoom(ctx context.Context, c *app.RequestContext) {
    var req model.CreateRoomReq  // 定义在 model/room.go
    ...
}
```

**缓解方案**：
- 用 Go AST 工具（`go/parser`）预扫描 import 路径和类型引用
- 把被引用的 struct 定义提取出来，注入到 prompt 中
- Code Graph 的代码库扫描能力可以提供这些跨文件引用

### 6.2 Import 依赖链

```go
import (
    "example/kitex_gen/room/service"  // 生成代码
    "example/dal"                      // 数据访问层
    "example/rpc"                      // RPC 客户端
)
```

LLM 无法自动解析 import 路径对应的代码。需要 Code Graph 提供函数级调用链数据来补充。

### 6.3 Middleware 逻辑

Hertz 的 middleware 会影响请求/响应，但不在 handler 代码中体现：

```go
// 鉴权 middleware 可能会注入 user_id
func AuthMiddleware() app.HandlerFunc {
    return func(ctx context.Context, c *app.RequestContext) {
        userID := extractUserFromToken(c)
        c.Set("user_id", userID)  // 注入上下文
        c.Next(ctx)
    }
}
```

Handler 中通过 `c.GetInt64("user_id")` 获取——LLM 看不到这个字段从哪来。

**缓解**：维护一个常见 middleware 注入字段的列表，作为 prompt 上下文注入。

### 6.4 生成代码（kitex_gen/）

Kitex 的 `kitex_gen/` 目录是自动生成的，struct 定义在这里但没有注释。IDL 中的注释不会传递到生成代码。

**缓解**：优先分析 IDL 文件而非生成代码；如果只有生成代码，LLM 从字段命名推断语义。

### 6.5 动态路由和反射

```go
// 动态注册路由
for _, api := range config.APIs {
    h.POST(api.Path, genericHandler(api.ServiceName, api.Method))
}
```

LLM 无法理解运行时动态注册的路由。这类情况需要运行时采集或配置文件解析。

---

## 7. 提取精度预估

基于上述分析，对不同提取目标的精度预估：

| 提取目标 | 预估精度 | 前提条件 |
|----------|---------|---------|
| API 名称 + HTTP method/route | **95%+** | 标准 Hertz 注解/Kitex IDL |
| 请求/响应字段名 + 类型 | **98%+** | struct 定义在当前文件或已注入 |
| 字段 JSON 序列化名 | **99%+** | 有 json tag |
| 字段语义描述 | **85-90%** | 命名规范 + 有注释时更高 |
| 字段敏感性分类 | **80-85%** | 常见模式（phone/email/password）高，业务特定的低 |
| 下游 RPC 调用识别 | **90%+** | client 变量命名清晰 |
| 字段到下游的映射 | **85-90%** | 直接赋值时高，经过转换时低 |
| Middleware 注入字段 | **30-40%** | 需要额外上下文 |

### 7.1 提升精度的关键策略

```
1. AST 预处理：用 go/parser 提取 struct 定义、import 关系 → 注入 prompt
2. IDL 优先：Kitex 服务优先分析 Thrift IDL 而非 Go 代码
3. Code Graph 上下文：注入被调用函数的签名信息
4. 内部术语表：维护字节内部术语（PSM/BOE/TOS 等）的解释
5. 多轮验证：对高敏感字段（PII）用 2-3 次独立调用取共识
6. 人工反馈循环：定期抽检，把 LLM 错误案例加入 few-shot 示例
```

---

## 8. 小结

### 8.1 Hertz vs Kitex 提取难度对比

| 维度 | Hertz（HTTP） | Kitex（RPC） |
|------|-------------|-------------|
| 接口定义来源 | 注解 + struct | **Thrift IDL**（更结构化）✅ |
| 字段类型明确性 | Go struct tag | IDL field + required/optional ✅ |
| 路由信息 | `@router` 注释 | IDL service 定义 ✅ |
| 字段映射追踪 | handler 内赋值 | handler 内赋值 |
| 提取难度 | 中等 | **较低**（IDL 是天然结构化数据）✅ |

**好消息**：字节以 Kitex 为主——Thrift IDL 提供了天然的结构化接口定义，LLM 甚至不需要"理解"代码，只需要"翻译" IDL 即可获得大量准确信息。

### 8.2 推荐的提取 Pipeline

```
Step 1: 从 Thrift IDL 提取接口定义和字段 schema（AST 工具，无需 LLM）
Step 2: 从 Go Handler 代码提取字段映射关系（LLM）
Step 3: 从 Code Graph 获取跨服务调用链（API 查询）
Step 4: LLM 综合上下文生成字段语义描述和敏感性分类
Step 5: 人工抽检高风险字段
```

这种分层策略可以最大化精度、最小化 LLM 成本。

---

*最后更新: 2026-03-05*
*参考: CloudWeGo Hertz 文档、Kitex 文档、Thrift IDL 规范*
