## Life++ 项目简介

Life++ 是一个基于 Revive / PolkaVM 的 **认知智能体网络与任务市场** Demo，用来展示：

- 多个长期运行的智能体（Agents）如何被注册、发现和调度；
- 任务如何在链下被认领、执行，在链上完成托管与结算（IVE 奖励）；
- 用户如何通过 Web 前端观察任务执行过程、记忆变化以及网络结构。

> 本 README 只面向本地开发 / 演示环境，不覆盖生产部署。

---

## 功能概览

### Dashboard

**功能**：总览当前系统的核心指标与运行状态。

- **全局状态**：展示 Agent 数量、在线状态、任务完成数等汇总信息。
- **最近活动**：最近创建/完成的任务、最新的记忆变化等。
- **入口导航**：跳转到 `AgentChat`、`MemoryViewer`、`Marketplace`、`NetworkGraph` 等模块。

> ![Dashboard 总览](images/image-20260315202730189.png)

---

### AgentChat

**功能**：与智能体进行对话、下达指令。

- **多 Agent 管理**：选择不同的 Agent，与之单独对话。
- **对话上下文**：查看历史消息和 Agent 的思考/回复。
- **任务触发**：在对话中触发任务创建或改变 Agent 配置。

> ![AgentChat 对话界面](images/image-20260315202756910.png)

---

### MemoryViewer

**功能**：查看与调试 Agent 的记忆与知识库。

- **记忆列表**：按时间、重要性查看 Agent 的记忆条目。
- **向量搜索**：在界面中搜索相关记忆，验证检索效果。
- **调试用途**：排查 Agent 为什么会做出某个决策。

> ![MemoryViewer 记忆视图](images/image-20260315202811845.png)

---

### Marketplace

**功能**：任务发布、认领与结算的核心模块。

- **发布任务**：
  - 通过前端填写标题、描述、奖励 IVE 数量；
  - 由浏览器钱包（MetaMask）发起 `createTask`，在 Revive 链上锁定奖励。
- **任务认领**：
  - 不同 Agent 所属用户可以选择任务并认领；
  - 后端用 relayer（deployer）账户调用 `acceptTaskFor`。
- **任务完成**：
  - 发布者点击 `Complete`；
  - 后端根据链上状态调用 `completeTask` / `completeTaskFor`，发放 IVE 奖励。
- **状态流转**：
  - `open → accepted → completed / cancelled`，前端有对应状态标签与进度条。

> ![Marketplace 任务市场](images/image-20260315203011584.png)

---

### NetworkGraph

**功能**：展示智能体网络结构与交互关系。

- **节点**：每个 Agent 一个节点，带有基本信息（名称、状态）。
- **连接关系**：展示 Agent 之间的连接/协作关系。
- **拓扑视图**：用于观察整个网络的结构与健康度。

> ![NetworkGraph 网络拓扑](images/image-20260315203040623.png)

---

## 本地启动教程

> 前置依赖：`git`、`Python 3.11+`、`Node.js 18+`、`npm`、`Docker`。

### 1. 克隆与初始化

```bash
git clone https://github.com/qnnnd/Polk2.0-Revive-Hackathon-Lifepp.git
cd Polk2.0-Revive-Hackathon-Lifepp
```

### 2. 启动数据库与缓存

项目使用 Docker 启动 PostgreSQL（带 pgvector）与 Redis：

```bash
docker compose up -d postgres redis
```

### 3. 启动 Revive 本地链（简化版说明）

> 这里仅给出高层说明，具体命令请根据你本地的 Revive 环境调整。

- 启动 Revive 本地节点（`revive-dev-node` + `eth-rpc`）。
- 部署合约（AgentRegistry、TaskMarket、Reputation），记录 `deployments.json` 中的地址。
- 确保 `.env` 中的链配置与部署信息一致（见下方“环境变量”）。

### 4. 配置 backend 环境变量

在 `backend/.env` 中配置（示例）：

```env
ENVIRONMENT=development
DEBUG=true

DATABASE_URL=postgresql+asyncpg://lifeplusplus:lifeplusplus@localhost:5432/lifeplusplus
REDIS_URL=redis://localhost:6379/0

REVIVE_RPC_URL=http://127.0.0.1:8545
AGENT_REGISTRY_ADDRESS=0x...
TASK_MARKET_ADDRESS=0x...
REPUTATION_ADDRESS=0x...
REVIVE_DEPLOYER_PRIVATE_KEY=0x...   # 部署 TaskMarket 的私钥
```

### 5. 启动 backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Backend 默认监听 `http://localhost:8002`，健康检查路径为 `/health`。

### 6. 启动 frontend

```bash
cd frontend
npm install
npm run dev  # 默认 http://localhost:3001
```

浏览器访问 `http://localhost:3001/marketplace`，即可看到任务市场与其他模块入口。

---

## 技术架构概览

### 分层结构

- **Frontend（Next.js / React）**
  - 页面：`/dashboard`、`/agentchat`、`/memory`, `/marketplace`, `/network`
  - UI 组件：`Topbar`、任务卡片、网络图渲染等
  - 数据获取：`react-query` + REST API

- **Backend（FastAPI + SQLAlchemy）**
  - 路由：`/api/v1/auth`, `/agents`, `/tasks`, `/marketplace`, `/memories`, `/network`, `/chain`
  - 服务层：`chain_service.py` 负责与 Revive 节点交互
  - 数据层：PostgreSQL + pgvector 存储 Agent、记忆、任务与声誉

- **Chain（Revive / PolkaVM）**
  - 合约：`TaskMarket.sol`、`AgentRegistry.sol`、`Reputation.sol`
  - 功能：任务托管、奖励发放、链上声誉记录

---

## 主要流程（简化）

### 1. 发布任务流程

1. 用户在前端填写任务信息（标题、描述、奖励）。
2. 前端调用 `/api/v1/tasks` 创建 listing，backend 生成 `createTask` 的链上 tx 参数。
3. 前端用 MetaMask 发送 `createTask`，锁定 IVE 奖励。
4. 前端将 `tx_hash` 回传给 backend，backend 解析事件得到 `taskId` 并写入 `chain_task_id`。

### 2. 认领任务流程

1. Worker 选择一个 Agent 与任务，在前端点击 `Accept`。
2. Backend 使用 relayer 私钥调用 `acceptTaskFor`，链上将任务状态改为 `Accepted`，记录 rewardRecipient。
3. DB 中将 listing 状态改为 `accepted`，创建对应的 `Task` 记录。

### 3. 完成任务流程

1. 发布者确认任务完成，在前端点击 `Complete`。
2. Backend 调用 `complete_task_on_chain`：
   - 根据链上 poster / status 选择 `completeTask` 或 `completeTaskFor`；
   - 幂等处理：若链上已是 `Completed`，直接视为成功。
3. 不论链上结果如何，DB 中都会将 listing / task 状态更新为 `completed`；
4. 如果链上成功，额外记录 `Reputation.recordTaskComplete`。

---

## 使用的技术组件

- **前端**
  - Next.js 14 / React
  - TypeScript
  - @tanstack/react-query（数据获取与缓存）
  - sonner（Toast 通知）

- **后端**
  - FastAPI
  - SQLAlchemy / asyncpg
  - Redis（缓存 / 队列）
  - web3.py（与 Revive / PolkaVM 交互）

- **链 & 基础设施**
  - Revive 本地链 / PolkaVM
  - Hardhat（合约编译与部署）
  - PostgreSQL + pgvector
  - Docker / docker compose

---

## 备注

- 本仓库包含了一些面向开发者/测试的脚本与配置（如 `scripts/e2e_task_cog_test.py`），如需了解更细的测试流程，可以直接阅读对应脚本。
- 如果你在本地运行时遇到链上交易失败（例如 Revive 节点未启动、余额不足等），任务在 DB 中仍会完成，但 IVE 奖励不会真正发放，请结合日志与链上状态排查。

