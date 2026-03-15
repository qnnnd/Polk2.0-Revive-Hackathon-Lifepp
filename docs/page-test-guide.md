# 页面功能测试指南

在浏览器里按下面步骤逐项验证 Life++ 各功能（前端：http://localhost:3001，后端：http://localhost:8002）。

## 前置条件

- 后端已启动：`cd backend && source .venv/bin/activate && python main.py`（端口 8002）
- 前端已启动：`cd frontend && npm run dev`（端口 3001）
- Docker：Postgres、Redis 已运行（`docker compose up -d postgres redis`）
- 若测链上功能：本地 Revive（revive-dev-node + eth-rpc）已起，合约已部署并执行过 `./scripts/apply-revive-local-env.sh`

---

## 1. 登录与钱包

**主要作用**：完成应用内身份认证（用户名 + JWT），并将当前用户与链上钱包地址绑定，用于后续查看 COG 余额、链上身份展示等。

| 步骤 | 操作 | 预期 |
|------|------|------|
| 1.1 | 打开 http://localhost:3001/dashboard | 看到「Choose a username」和「Enter Life++」 |
| 1.2 | 输入用户名（如 `alice`），点击「Enter Life++」 | 进入 Dashboard，侧边栏和统计卡片正常显示 |
| 1.3 | 点击右上角「Connect MetaMask」 | 弹出 MetaMask 授权，选账户后按钮变为短地址（如 `0x3cd0...c6e0`） |
| 1.4 | 再次点击钱包地址 | 出现菜单：「Switch account」「Disconnect」 |
| 1.5 | 点击「Disconnect」 | 钱包断开，按钮恢复为「Connect MetaMask」 |

---

## 2. Dashboard

**主要作用**：总览 Agent 数量、在线状态、待办任务、Revive 链状态等；创建新 Agent 并进入 Agent 列表与任务概览。

| 步骤 | 操作 | 预期 |
|------|------|------|
| 2.1 | 登录后停留在 Dashboard | 看到「Persistent Agent + Memory + Task Market」、Revive 状态、统计卡片 |
| 2.2 | 查看「Revive Testnet Status」 | 若链已配置：显示 Online/Offline、Agents on chain；未配置则显示 Not configured |
| 2.3 | 点击「+ New Agent」 | 成功创建 Agent，列表中出现新 Agent 卡片 |

---

## 3. AgentChat（侧边栏）

**主要作用**：选择某个 Agent 后与其进行对话；支持多轮聊天、记忆写入与召回（由后端 AI 或 mock 回复），消息持久化。

| 步骤 | 操作 | 预期 |
|------|------|------|
| 3.1 | 点击侧边栏「AgentChat」 | 主区切换为 Agent 列表（选择 Agent 聊天） |
| 3.2 | 点击某个 Agent 卡片「Chat →」 | 跳转到 `/agents/[id]`，进入该 Agent 的聊天页 |
| 3.3 | 在输入框输入消息（如「记住我喜欢 AI 研究」），发送 | 收到回复（无 API Key 时为 mock 回复），消息持久显示 |

---

## 4. MemoryViewer（侧边栏）

**主要作用**：按 Agent 查看其持久化记忆（episodic / semantic 等类型），支持语义搜索与记忆整合（Consolidate），便于验证记忆存储与检索。

| 步骤 | 操作 | 预期 |
|------|------|------|
| 4.1 | 点击侧边栏「MemoryViewer」 | 主区显示「Select agent」下拉 + 记忆列表 |
| 4.2 | 选择不同 Agent | 记忆列表随所选 Agent 变化 |
| 4.3 | 在搜索框输入关键词（如「AI」） | 出现语义检索结果（若该 Agent 有相关记忆） |
| 4.4 | 点击「Consolidate」 | 执行记忆整合（无报错即可） |

---

## 5. Marketplace

**主要作用**：任务市场：发布带 COG 奖励的任务、查看任务列表与状态、认领/取消/完成任务，并与 Revive 链上 TaskMarket 合约联动实现链上结算。

| 步骤 | 操作 | 预期 |
|------|------|------|
| 5.1 | 点击侧边栏「Marketplace」 | 进入任务市场页 |
| 5.2 | 填写任务标题、描述、COG 奖励，点击「Publish Task」 | 任务创建成功，列表中能看到新任务及状态 |
| 5.3 | 查看任务列表 | 状态标签（open / pending / completed 等）、COG 奖励显示正确 |
| 5.4 | 对自家任务点击「Cancel」 | 任务可取消（状态更新） |
| 5.5 | 发布者点击「Complete」确认已完成 | 任务状态变为 completed；若链已配置，任务卡片下会显示 TX: &lt;hash&gt; |

### 5.6 如何确认代币（COG）是否发放

- **任务卡片**：完成的任务若走链上结算，会显示 **TX: 0x...**；有该 hash 表示链上 `completeTask` 已成功，合约已将 COG 转给**认领时连接的钱包**（rewardRecipient）。
- **链上设计**：认领时后端会把**当前用户已连接的钱包地址**写入合约的 rewardRecipient；完成时 COG 从 TaskMarket 合约转给该地址。因此认领者必须在认领前在应用内**连接钱包**（如 MetaMask），且完成时收到 COG 的是**认领时绑定的那个地址**。
- **认领者看不到 COG 时请排查**：
  1. **奖励使用原生 IVE**：任务奖励为链上原生代币 IVE，无需添加 ERC-20；认领方完成后的收款地址会收到 IVE。
  2. **认领与查看是否同一账户**：收到 COG 的是在 Life++ 里点击认领时已连接并绑定的钱包地址；若在扩展里切换了账户，请确认当前选中的账户与当时认领一致。
  3. **任务是否在新合约上完成**：若任务是在**重新部署合约之前**认领/完成的，当时链上仍可能把奖励发给 deployer；请用**新发布并新认领**的任务再测一遍。
- **应用内**：接任务方的 Agent 声誉会更新（Dashboard / Agent 详情中的 tasks completed、total_cog_earned 等）。奖励单位为 IVE。

---

## 6. NetworkGraph

**主要作用**：以图形式展示所有公开 Agent 及其关系；节点大小可反映声誉，点击节点可查看详情，用于理解网络拓扑与 Agent 协作关系。

| 步骤 | 操作 | 预期 |
|------|------|------|
| 6.1 | 点击侧边栏「NetworkGraph」 | 进入网络图页，看到 Agent 节点与连线 |
| 6.2 | 点击某个节点 | 显示该 Agent 的详情（状态、能力、声誉等） |

---

## 7. 链上与 API 校验（可选）

**主要作用**：通过 Swagger 调用后端 API、查询链配置与余额，并用脚本校验链上数据（合约、Agent 注册、任务、声誉等），确保无假数据、符合「必须使用 Revive」要求。

| 步骤 | 操作 | 预期 |
|------|------|------|
| 7.1 | 打开 http://localhost:8002/docs | Swagger UI 正常，可尝试 GET /api/v1/chain/config、/chain/stats（无需登录） |
| 7.2 | 登录后请求 GET /api/v1/chain/balance（在 Swagger 里带 Bearer token） | 若已连接钱包且链已配置，返回 COG 余额 |
| 7.3 | 在项目根目录执行 `./scripts/verify-chain-data.sh` | 脚本检查链连接、合约地址、Agent 数量、任务与声誉等（链已部署时通过） |

---

## 8. E2E 任务与代币脚本（Test-Creator / Test-Worker）

**用途**：用用户 A（Test-Creator）、B（Test-Worker）自动跑完「发布 → 认领 → 完成」并校验 COG 扣款与发放。

| 步骤 | 命令 | 说明 |
|------|------|------|
| 8.1 | `./backend/.venv/bin/python scripts/e2e_task_cog_test.py --no-chain` | 仅验证 API 流程（reward=0，不依赖链）；A 发任务 → B 认领 → A 完成，再 B 发 → A 认领 → B 完成 |
| 8.2 | `./backend/.venv/bin/python scripts/e2e_task_cog_test.py` | 完整流程：带 IVE 奖励、链上扣款与发放。需本地 Revive 节点接受交易（若出现 1010/1012 则链未放行，先跑 8.1 验证接口） |

用户 A 地址：`0xf24FF3a9CF04c71Dbc94D0b566f7A27B94566cac`，用户 B：`0x3Cd0A705a2DC65e5b1E1205896BaA2be8A07c6e0`。脚本会先为两者设置钱包并拉取 Agent，再按阶段发布/认领/完成并（在非 `--no-chain` 时）校验 deployer 与 B/A 的 COG 余额变化。

---

## 快速检查清单

- [ ] 登录 / 登出（用户名 + Enter Life++）
- [ ] 钱包连接 / 切换账号 / 断开
- [ ] Dashboard 统计与创建 Agent
- [ ] AgentChat：列表 → 进入聊天 → 发消息收回复
- [ ] MemoryViewer：选 Agent、搜索记忆、Consolidate
- [ ] Marketplace：发布任务、列表、取消
- [ ] NetworkGraph：图加载、点击节点详情
- [ ] Revive 状态与链上校验（在链已配置时）

完成以上步骤即完成主要页面功能测试。
