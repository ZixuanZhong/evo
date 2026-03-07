#!/usr/bin/env python3
"""
extraction-prompts.py — LLM Prompt Engineering for Go-Kitex API Semantic Extraction

This script defines the complete prompt pipeline for extracting API schema
and field semantics from Go-Kitex handler code using LLMs.

It does NOT call any LLM API — it prints the fully assembled prompts
and demonstrates the expected output format with mock responses.

Usage:
    python3 extraction-prompts.py
"""

import json
from typing import Any

# =============================================================================
# OUTPUT SCHEMA — JSON Schema defining the expected LLM output format
# =============================================================================

OUTPUT_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "APISemanticExtraction",
    "description": "Structured extraction of API semantics from Go-Kitex handler code",
    "type": "object",
    "required": ["service_name", "apis"],
    "properties": {
        "service_name": {
            "type": "string",
            "description": "Name of the microservice"
        },
        "apis": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["api_name", "framework", "request_schema", "response_schema"],
                "properties": {
                    "api_name": {"type": "string"},
                    "framework": {"type": "string", "enum": ["hertz", "kitex"]},
                    "http_method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"]},
                    "route": {"type": "string"},
                    "request_schema": {
                        "type": "object",
                        "properties": {
                            "struct_name": {"type": "string"},
                            "fields": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["name", "go_type", "semantic", "sensitivity"],
                                    "properties": {
                                        "name": {"type": "string"},
                                        "go_type": {"type": "string"},
                                        "json_name": {"type": "string"},
                                        "semantic": {"type": "string", "description": "Chinese business meaning"},
                                        "sensitivity": {
                                            "type": "string",
                                            "enum": ["none", "pii", "financial", "internal_id"]
                                        },
                                        "required": {"type": "boolean"}
                                    }
                                }
                            }
                        }
                    },
                    "response_schema": {"$ref": "#/properties/apis/items/properties/request_schema"},
                    "downstream_calls": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "service": {"type": "string"},
                                "method": {"type": "string"},
                                "field_mapping": {
                                    "type": "object",
                                    "additionalProperties": {"type": "string"}
                                }
                            }
                        }
                    },
                    "db_operations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "table": {"type": "string"},
                                "operation": {"type": "string", "enum": ["read", "write", "update", "delete"]},
                                "field_mapping": {
                                    "type": "object",
                                    "additionalProperties": {"type": "string"}
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}


# =============================================================================
# SYSTEM PROMPT — Instructs the LLM on how to analyze Go code
# =============================================================================

SYSTEM_PROMPT = """你是一个代码语义分析助手，专注于分析 Go-Kitex/Hertz 微服务代码。

你的任务是从 Go handler 代码中提取 API 的结构化语义信息，输出严格的 JSON 格式。

## 提取规则

1. **service_name**: 从 struct 实现名称或包名推断服务名（如 UserServiceImpl → user-service）
2. **api_name**: handler 函数名（如 GetUserProfile, SendGift）
3. **framework**: 识别框架——有 Thrift IDL struct 的是 kitex，有 @router 的是 hertz
4. **request_schema / response_schema**: 提取所有字段，包括：
   - name: Go 字段名
   - go_type: Go 类型（int64, string, bool 等）
   - json_name: JSON tag 中的名称（如果有）
   - semantic: **必须用中文**描述字段的业务含义，不要只翻译字段名
   - sensitivity: 敏感性分类
     - pii: 手机号、身份证、邮箱、地址、姓名等个人可识别信息
     - financial: 余额、金额、收入、支出等金融数据
     - internal_id: 内部系统 ID（user_id, room_id 等）
     - none: 其他
   - required: 是否必填（Thrift 的 required/optional，或 Go validate tag）
5. **downstream_calls**: 识别 RPC 客户端调用（如 s.paymentClient.Deduct）
   - service: 下游服务名
   - method: 调用的方法名
   - field_mapping: 本地字段 → 下游请求字段的映射
6. **db_operations**: 识别数据库操作（GORM 的 Create/Where/Updates 等）
   - table: 表名（从 TableName() 或 GORM model 推断）
   - operation: read/write/update/delete
   - field_mapping: API 字段 → DB 列的映射

## 输出格式

严格输出 JSON，不要添加任何解释文字。schema 如下：
""" + json.dumps(OUTPUT_SCHEMA, indent=2, ensure_ascii=False)


# =============================================================================
# FEW-SHOT EXAMPLES — One complete input/output pair for format calibration
# =============================================================================

FEW_SHOT_INPUT = '''```go
// handler.go — RoomService

type RoomServiceImpl struct {
    db *gorm.DB
}

// CreateRoom 创建直播间
func (s *RoomServiceImpl) CreateRoom(ctx context.Context, req *service.CreateRoomRequest) (*service.CreateRoomResponse, error) {
    roomID, err := dal.InsertRoom(ctx, dal.Room{
        AnchorID: req.AnchorID,
        Title:    req.Title,
        Category: req.GetCategory(),
    })
    if err != nil {
        return nil, err
    }
    return &service.CreateRoomResponse{RoomID: roomID, Status: "created"}, nil
}

// Thrift IDL (context):
// struct CreateRoomRequest {
//     1: required i64 anchor_id   // 主播 ID
//     2: required string title    // 直播间标题
//     3: optional i32 category    // 分类 ID
// }
// struct CreateRoomResponse {
//     1: required i64 room_id     // 直播间 ID
//     2: required string status   // 直播间状态
// }
```'''

FEW_SHOT_OUTPUT = {
    "service_name": "room-service",
    "apis": [
        {
            "api_name": "CreateRoom",
            "framework": "kitex",
            "request_schema": {
                "struct_name": "CreateRoomRequest",
                "fields": [
                    {
                        "name": "AnchorID",
                        "go_type": "int64",
                        "json_name": "anchor_id",
                        "semantic": "创建直播间的主播用户 ID",
                        "sensitivity": "internal_id",
                        "required": True
                    },
                    {
                        "name": "Title",
                        "go_type": "string",
                        "json_name": "title",
                        "semantic": "直播间标题，用户可见的显示名称",
                        "sensitivity": "none",
                        "required": True
                    },
                    {
                        "name": "Category",
                        "go_type": "int32",
                        "json_name": "category",
                        "semantic": "直播间分类 ID，如游戏、唱歌、聊天等",
                        "sensitivity": "none",
                        "required": False
                    }
                ]
            },
            "response_schema": {
                "struct_name": "CreateRoomResponse",
                "fields": [
                    {
                        "name": "RoomID",
                        "go_type": "int64",
                        "json_name": "room_id",
                        "semantic": "新创建的直播间唯一标识 ID",
                        "sensitivity": "internal_id",
                        "required": True
                    },
                    {
                        "name": "Status",
                        "go_type": "string",
                        "json_name": "status",
                        "semantic": "直播间当前状态（如 created, live, closed）",
                        "sensitivity": "none",
                        "required": True
                    }
                ]
            },
            "downstream_calls": [],
            "db_operations": [
                {
                    "table": "rooms",
                    "operation": "write",
                    "field_mapping": {
                        "AnchorID": "anchor_id",
                        "Title": "title",
                        "Category": "category"
                    }
                }
            ]
        }
    ]
}


# =============================================================================
# TEST INPUT — Real handler code from mock-services-impl (payment-service)
# =============================================================================

TEST_INPUT_PAYMENT_SERVICE = '''```go
// payment-service handler.go + dal/wallet.go

// --- GORM Model ---
type WalletModel struct {
    UserID       int64 `gorm:"column:user_id;primaryKey"` // 用户 ID
    Balance      int64 `gorm:"column:balance"`            // 余额（分）—— Financial
    TotalIncome  int64 `gorm:"column:total_income"`       // 累计收入 —— Financial
    TotalExpense int64 `gorm:"column:total_expense"`      // 累计支出 —— Financial
    UpdatedAt    int64 `gorm:"column:updated_at"`
}
func (WalletModel) TableName() string { return "wallets" }

// --- Handler ---
type PaymentServiceImpl struct { db *gorm.DB }

// Deduct 扣减用户余额
// 由 gift-service 调用，字段传播：DeductRequest.user_id → wallets.user_id
func (s *PaymentServiceImpl) Deduct(ctx context.Context, req *payment.DeductRequest) (*payment.DeductResponse, error) {
    remainingBalance, err := dal.DeductBalance(ctx, s.db, req.UserId, req.Amount)
    if err != nil {
        if err.Error() == "insufficient balance" {
            return &payment.DeductResponse{Code: 2001, Message: strPtr("余额不足")}, nil
        }
        return &payment.DeductResponse{Code: 500, Message: strPtr("扣款失败")}, nil
    }
    return &payment.DeductResponse{
        Code: 0, Message: strPtr("success"),
        RemainingBalance: &remainingBalance, // Financial: 返回剩余余额
    }, nil
}

// GetBalance 查询用户余额
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

// --- Thrift IDL (context) ---
// struct DeductRequest {
//     1: required i64 user_id         // 被扣款的用户 ID
//     2: required i64 amount          // 扣款金额（分）
//     3: required string reason       // 扣款原因
//     4: optional string idempotent_key // 幂等键
// }
// struct DeductResponse {
//     1: required i32 code
//     2: optional string message
//     3: optional i64 remaining_balance // 扣款后剩余余额（分）—— 金融敏感
// }
// struct GetBalanceRequest { 1: required i64 user_id }
// struct GetBalanceResponse { 1: required i32 code  2: optional string message  3: optional Wallet wallet }
// struct Wallet {
//     1: required i64 user_id  2: required i64 balance  3: required i64 total_income
//     4: required i64 total_expense  5: required i64 updated_at
// }
```'''

# Mock response simulating what an LLM would return for the payment-service input
MOCK_RESPONSE_PAYMENT = {
    "service_name": "payment-service",
    "apis": [
        {
            "api_name": "Deduct",
            "framework": "kitex",
            "request_schema": {
                "struct_name": "DeductRequest",
                "fields": [
                    {"name": "UserId", "go_type": "int64", "json_name": "user_id",
                     "semantic": "被扣款的用户 ID，由上游 gift-service 传入", "sensitivity": "internal_id", "required": True},
                    {"name": "Amount", "go_type": "int64", "json_name": "amount",
                     "semantic": "扣款金额，单位为分", "sensitivity": "financial", "required": True},
                    {"name": "Reason", "go_type": "string", "json_name": "reason",
                     "semantic": "扣款原因描述，如 send_gift 表示送礼扣款", "sensitivity": "none", "required": True},
                    {"name": "IdempotentKey", "go_type": "string", "json_name": "idempotent_key",
                     "semantic": "幂等键，防止网络重试导致重复扣款", "sensitivity": "none", "required": False}
                ]
            },
            "response_schema": {
                "struct_name": "DeductResponse",
                "fields": [
                    {"name": "Code", "go_type": "int32", "json_name": "code",
                     "semantic": "错误码，0 表示成功，2001 表示余额不足", "sensitivity": "none", "required": True},
                    {"name": "Message", "go_type": "string", "json_name": "message",
                     "semantic": "错误描述信息", "sensitivity": "none", "required": False},
                    {"name": "RemainingBalance", "go_type": "int64", "json_name": "remaining_balance",
                     "semantic": "扣款后用户的剩余余额，单位为分", "sensitivity": "financial", "required": False}
                ]
            },
            "downstream_calls": [],
            "db_operations": [
                {
                    "table": "wallets",
                    "operation": "update",
                    "field_mapping": {
                        "UserId": "user_id (WHERE)",
                        "Amount": "balance (DECREMENT), total_expense (INCREMENT)"
                    }
                }
            ]
        },
        {
            "api_name": "GetBalance",
            "framework": "kitex",
            "request_schema": {
                "struct_name": "GetBalanceRequest",
                "fields": [
                    {"name": "UserId", "go_type": "int64", "json_name": "user_id",
                     "semantic": "要查询余额的用户 ID", "sensitivity": "internal_id", "required": True}
                ]
            },
            "response_schema": {
                "struct_name": "GetBalanceResponse",
                "fields": [
                    {"name": "Code", "go_type": "int32", "json_name": "code",
                     "semantic": "错误码", "sensitivity": "none", "required": True},
                    {"name": "Message", "go_type": "string", "json_name": "message",
                     "semantic": "错误描述", "sensitivity": "none", "required": False},
                    {"name": "Wallet", "go_type": "Wallet", "json_name": "wallet",
                     "semantic": "用户钱包详细信息，包含余额和收支统计", "sensitivity": "financial", "required": False}
                ]
            },
            "downstream_calls": [],
            "db_operations": [
                {
                    "table": "wallets",
                    "operation": "read",
                    "field_mapping": {
                        "UserId": "user_id (WHERE)"
                    }
                }
            ]
        }
    ]
}


# =============================================================================
# CORE FUNCTION — Assembles the full prompt for LLM extraction
# =============================================================================

def build_extraction_prompt(code: str, include_few_shot: bool = True) -> list[dict[str, str]]:
    """
    Build the complete message list for LLM API call.

    Args:
        code: Go source code string to analyze
        include_few_shot: Whether to include few-shot example (recommended)

    Returns:
        List of message dicts suitable for OpenAI/Anthropic chat API
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Add few-shot example for format calibration
    if include_few_shot:
        messages.append({"role": "user", "content": f"分析以下代码：\n\n{FEW_SHOT_INPUT}"})
        messages.append({"role": "assistant", "content": json.dumps(FEW_SHOT_OUTPUT, indent=2, ensure_ascii=False)})

    # Add the actual code to analyze
    messages.append({"role": "user", "content": f"分析以下代码：\n\n{code}"})

    return messages


def extract_api_semantics(code: str, mock: bool = True) -> dict:
    """
    Extract API semantics from Go handler code.

    In production, this would call an LLM API (GPT-4o / Claude Sonnet).
    In mock mode, it prints the prompt and returns a mock response.

    Args:
        code: Go source code to analyze
        mock: If True, print prompt and return mock; if False, would call LLM API

    Returns:
        Parsed JSON dict with API semantic extraction results
    """
    messages = build_extraction_prompt(code, include_few_shot=True)

    if mock:
        # Print the assembled prompt for inspection
        print("=" * 70)
        print("ASSEMBLED PROMPT (would be sent to LLM API)")
        print("=" * 70)
        for i, msg in enumerate(messages):
            role = msg["role"].upper()
            content_preview = msg["content"][:200] + "..." if len(msg["content"]) > 200 else msg["content"]
            print(f"\n[Message {i}] {role}:")
            print(content_preview)
        print("\n" + "=" * 70)

        # Return mock response
        return MOCK_RESPONSE_PAYMENT
    else:
        # Production path — call LLM API
        # Example with OpenAI:
        #   from openai import OpenAI
        #   client = OpenAI()
        #   response = client.chat.completions.create(
        #       model="gpt-4o",
        #       messages=messages,
        #       response_format={"type": "json_object"},
        #       temperature=0.1,  # Low temp for deterministic extraction
        #   )
        #   return json.loads(response.choices[0].message.content)
        raise NotImplementedError("Set mock=False requires LLM API credentials")


def validate_extraction(result: dict) -> list[str]:
    """
    Validate extraction results against expected patterns.
    Returns a list of issues found (empty = all good).
    """
    issues = []

    if "service_name" not in result:
        issues.append("Missing service_name")

    for api in result.get("apis", []):
        api_name = api.get("api_name", "unknown")

        # Check all fields have semantic descriptions
        for schema_key in ["request_schema", "response_schema"]:
            schema = api.get(schema_key, {})
            for field in schema.get("fields", []):
                if not field.get("semantic"):
                    issues.append(f"{api_name}.{schema_key}: field '{field.get('name')}' missing semantic")
                if field.get("sensitivity") not in ("none", "pii", "financial", "internal_id"):
                    issues.append(f"{api_name}.{schema_key}: field '{field.get('name')}' invalid sensitivity")

    return issues


def compute_extraction_stats(result: dict) -> dict:
    """Compute statistics from extraction results for quality metrics."""
    stats = {
        "total_apis": 0,
        "total_fields": 0,
        "pii_fields": 0,
        "financial_fields": 0,
        "downstream_calls": 0,
        "db_operations": 0,
    }

    for api in result.get("apis", []):
        stats["total_apis"] += 1
        for schema_key in ["request_schema", "response_schema"]:
            for field in api.get(schema_key, {}).get("fields", []):
                stats["total_fields"] += 1
                if field.get("sensitivity") == "pii":
                    stats["pii_fields"] += 1
                elif field.get("sensitivity") == "financial":
                    stats["financial_fields"] += 1
        stats["downstream_calls"] += len(api.get("downstream_calls", []))
        stats["db_operations"] += len(api.get("db_operations", []))

    return stats


# =============================================================================
# MAIN — Demo the extraction pipeline with mock services
# =============================================================================

def main():
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  Ontology Pipeline — LLM Extraction Prompt Engineering PoC ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()

    # --- Step 1: Extract API semantics from payment-service ---
    print("[Step 1] Extracting API semantics from payment-service handler...")
    print()

    result = extract_api_semantics(TEST_INPUT_PAYMENT_SERVICE, mock=True)

    # --- Step 2: Show extracted result ---
    print("\n[Step 2] Extraction result (mock LLM response):")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # --- Step 3: Validate ---
    print("\n[Step 3] Validating extraction result...")
    issues = validate_extraction(result)
    if issues:
        print(f"  ⚠️  Found {len(issues)} issues:")
        for issue in issues:
            print(f"    - {issue}")
    else:
        print("  ✅ Validation passed — all fields have semantics and valid sensitivity")

    # --- Step 4: Statistics ---
    print("\n[Step 4] Extraction statistics:")
    stats = compute_extraction_stats(result)
    print(f"  APIs extracted:      {stats['total_apis']}")
    print(f"  Total fields:        {stats['total_fields']}")
    print(f"  PII fields:          {stats['pii_fields']}")
    print(f"  Financial fields:    {stats['financial_fields']}")
    print(f"  Downstream calls:    {stats['downstream_calls']}")
    print(f"  DB operations:       {stats['db_operations']}")

    # --- Step 5: Compare with ground truth ---
    print("\n[Step 5] Ground truth comparison (payment-service):")
    expected_sensitive = {
        ("Wallet.balance", "financial"),
        ("Wallet.total_income", "financial"),
        ("Wallet.total_expense", "financial"),
        ("DeductRequest.amount", "financial"),
        ("DeductResponse.remaining_balance", "financial"),
    }
    found_sensitive = set()
    for api in result.get("apis", []):
        for schema_key in ["request_schema", "response_schema"]:
            for field in api.get(schema_key, {}).get("fields", []):
                if field.get("sensitivity") in ("pii", "financial"):
                    struct_name = api.get(schema_key, {}).get("struct_name", "")
                    found_sensitive.add((f"{struct_name}.{field['name'].lower()}", field["sensitivity"]))

    print(f"  Expected sensitive fields: {len(expected_sensitive)}")
    print(f"  Found sensitive fields:    {len(found_sensitive)}")
    print(f"  (Detailed comparison would require normalized field name matching)")

    # --- Step 6: Token usage estimate ---
    print("\n[Step 6] Estimated token usage:")
    prompt_text = SYSTEM_PROMPT + FEW_SHOT_INPUT + json.dumps(FEW_SHOT_OUTPUT) + TEST_INPUT_PAYMENT_SERVICE
    est_tokens = len(prompt_text) // 3  # rough estimate: ~3 chars per token for mixed content
    print(f"  Input tokens (est):  ~{est_tokens}")
    print(f"  Output tokens (est): ~500")
    print(f"  Cost (GPT-4o):       ~${est_tokens * 2.50 / 1_000_000 + 500 * 10.00 / 1_000_000:.4f}")
    print(f"  Cost (GPT-4o-mini):  ~${est_tokens * 0.15 / 1_000_000 + 500 * 0.60 / 1_000_000:.4f}")

    print("\n✅ PoC complete. In production, replace mock=True with actual LLM API call.")


if __name__ == "__main__":
    main()
