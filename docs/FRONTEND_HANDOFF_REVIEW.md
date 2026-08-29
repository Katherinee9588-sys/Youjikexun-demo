# 新手页前端交付包审查与接入边界

> 审查日期：2026-08-29  
> 输入：`/Users/catherine/Downloads/新手页前端代码包/`  
> 当前结论：视觉方向已落入主仓库的新手文字入口；录音、STT 与模型反馈仍保持为独立后续阶段。

## 0. 2026-08-29：第一阶段已直接收口

- 新增 `frontend/src/components/QuickEntryPage.tsx`，应用默认进入“记录”；
- 使用真实 `POST /api/entries` 保存 `record_date`、`original_text`、`input_method=text`；
- 保存响应通过最小运行时字段校验后，才进入“已保存”页面；
- 新手页状态为 `welcome / writing / saving / saved / error`，保存中禁用返回和提交；
- “健康数据”已使用真实 `button`，进入现有首页；
- 320px 默认态和文字输入态均无横向溢出；
- 没有接入交付包的 `multipart`、Mock、`latest` 依赖或假 AI 回复。

本阶段没有自动调用 `/api/companion`：记录落库成功与模型能否命中审核资料是两件事，不能绑成同一个“保存成功”状态。

## 1. 最省时的接入方式

不把代码退回设计反复修改，也不新建第二套前端工程。保留交付包作为视觉与样式来源，在现有 `frontend/` 中新增干净的新手入口模块，直接使用仓库已有 TypeScript 类型和 FastAPI 接口。原有首页、身体账本、发现和方案继续保留；“健康数据”进入现有首页。

设计同学后续只核对视觉，不负责重新设计数据结构或 API。

## 2. 可以复用

- 温和、克制的色彩和移动端视觉方向；
- 欢迎页标题、说明、麦克风主操作和会话页布局；
- `MediaRecorder`、长按、上滑取消的基础代码；
- Mock 与真实 Adapter 分开的意图；
- 固定安全说明和 reduced-motion 方向。

390 × 844 下视觉层级清楚，主操作明确。浏览器控制台没有发现前端运行错误。

## 3. 不能直接接入的阻塞项

### 3.1 API 契约不一致（文字阶段已解决）

交付包发送：

```text
POST {baseUrl}{recordPath}
multipart: audio, duration_ms
```

并期待：

```ts
{ recordId: string; userText: string; aiText: string; saved: boolean }
```

当前后端实际提供：

```text
POST /api/entries
JSON: record_date, original_text, input_method

POST /api/companion
JSON: user_text
```

当前文字入口已通过 `saveTextEntry()` 适配现有接口，并验证最小返回结构。音频上传或 STT 接口仍不存在，因此浏览器录音和未来 INMP441 都必须先得到真实转写文本，再复用 `POST /api/entries`；需要陪伴反馈时，再显式调用 `/api/companion`。

### 3.2 状态机没有闭环（交付包原问题）

- `ViewState` 没有独立 `sending`，发送时借用了 `error`；
- 返回任意 2xx 后直接进入会话，没有检查 `saved === true`；
- 发送中欢迎页仍可操作；
- 点击只切换视觉状态，真正录音只在长按 280ms 后开始；
- 上滑取消直接释放流，没有完整停止正在运行的 `MediaRecorder`；
- 响应 JSON 只有 TypeScript 断言，没有运行时字段检查。

文字入口不复用这套录音状态机，而是使用与当前能力对应的五态：`welcome / writing / saving / saved / error`。`saving` 期间不能重复提交；返回结构不符合账本条目时明确报错，不进入已保存页。

### 3.3 页面入口和响应式问题（第一阶段已解决）

- “健康数据 >”是无点击行为的 `div`，键盘和屏幕阅读器无法把它当作按钮；
- 320 × 640 下“开始记录”与“健康数据”发生遮挡；
- 缺少真实后端不可用时的禁用状态；
- 部分符号图标与视觉规范中“不使用 Emoji/字符代替正式功能图标”的要求不一致；
- 包名为 v4，但交接文档标题仍为 v3；依赖版本使用 `latest`，后续应固定版本。

主仓库没有接入交付包的依赖清单，继续使用现有锁文件。

## 4. 直接收口时的数据流

```text
文字输入
→ POST /api/entries，input_method=text
→ 后端确认原始记录已保存
→ 已保存页或健康数据首页

未来浏览器麦克风或 INMP441
→ 真实 STT 得到 transcript
→ 复用 POST /api/entries，input_method=voice 或 accessibility
→ 由用户触发的可选 POST /api/companion
```

没有真实 transcript 时不能显示“已保存”；RAG 或模型失败时显示真实错误，不回退到 Mock 文案。

## 5. 实施顺序

1. 已完成：文字 → `/api/entries` → 运行时响应校验 → 已保存；
2. 已完成：“健康数据”进入现有首页，复用视觉样式并修复 320px；
3. 下一步：由用户明确触发的 `/api/companion`，不与保存动作绑定；
4. STT 接口确定后再建立 `requesting_permission / recording / sending / saved / error` 的语音状态机；
5. INMP441 实机转写成功后复用同一文本入口，不另造账本格式。

## 6. 当前验收边界

- 交付包提供的静态产物可以渲染；
- 主仓库新手页已在 390px、320px 下复核，无横向溢出或遮挡；
- 本轮未能在独立临时目录完成依赖安装，因此没有把交付包源码的重新构建写成“已通过”；
- 主仓库自身的前端类型检查和生产构建独立通过；
- 主仓库按交付包视觉方向实现了新手页；未原样合入其录音/Mock/API 代码。
