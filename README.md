# Codex Title Updater

**让 Codex 的标题跟上对话，回头找聊天更方便**。<br>
**Keep Codex titles relevant as your conversation evolves, so chats are easier to find**.

第一轮只是开场，后面才聊到正题，侧栏标题却还停在开头。Codex Title Updater 在第一轮结束后先生成一个简洁中文标题，保留项目名和技术词；后续在主要话题变化、原标题已不准确时继续更新。<br>
The first exchange is often just a starting point. When the real task takes shape later, the sidebar title can lag behind. Codex Title Updater generates a concise Chinese title after the first turn, preserving project names and technical terms, then updates it when the main topic changes and the old title becomes inaccurate.

它通过 Codex 的 `Stop` Hook 在一轮结束时触发。首轮主动命名，无需先发生话题变化；后续标题仍然准确时保持不变，继续排错、测试或润色也不会仅因此换名。<br>
It runs through Codex's `Stop` hook at the end of a turn. The first turn gets an initial title without requiring a topic change. Later, accurate titles stay put, and routine debugging, testing or editing does not by itself trigger a rename.

## 复制提示词，让 Codex 安装 / Install with a prompt

适用于支持原生 Hooks 和 App Server 的已登录 Codex，需要 **Python 3.11+**。macOS 已验证；Linux 已通过单元测试，完整使用流程仍待验证；Windows 暂不支持。<br>
Requires a signed-in Codex with native Hooks and App Server, plus **Python 3.11+**. Verified on macOS; Linux unit tests pass, but the full workflow remains unverified. Windows is not supported yet.

把下面这段话发给 Codex，无需自己逐条执行安装命令：<br>
Paste this into Codex to have it handle the installation:

```text
请帮我安装 https://github.com/ye-kaifan/codex-title-updater。
先阅读 README，检查我的 Codex 和 Python 是否兼容，然后按仓库现有方案安装。
保留已有配置和其他 Hook，不要从头重写。
安装后检查注册、启用和信任状态，并用测试对话验证标题检查确实触发。
需要我手动审核信任时，请告诉我具体操作；完成后告诉我如何停用和恢复。
```

```text
Please install https://github.com/ye-kaifan/codex-title-updater for me.
Read the README, check my Codex and Python compatibility, then use the existing installer.
Preserve my configuration and other hooks; do not reimplement the project.
Check registration, enablement and trust, then verify that a title check runs in a test conversation.
Guide me through any manual trust review, and explain how to disable and re-enable it.
```

**安装后需在 `/hooks` 中审核并信任，才会运行**。 完成启用后，在新对话中完成一轮即可检查初次命名；若生成的标题与原标题完全相同，结果会是“保留”。<br>
**Review and trust the hook in `/hooks` before it can run**. Once enabled, complete one turn in a new conversation to check initial naming. If the generated title is identical to the existing one, the result is a successful keep.

标题判断会调用你在 Codex 中配置的模型服务，消耗额度或产生 API 费用，也可能增加轮末等待时间。<br>
Title reviews use your configured Codex model provider, consume quota or incur API charges, and may add a wait at the end of a turn.

## 标题什么时候会改 / When titles change

- **第一轮先命名**。 首轮结束后，根据实际需求和回答主动生成标题，不要求话题已变化。后续检查点为第 2、6、8、10…轮；每次成功改名都需冷却至少 4 轮。第一轮成功改名时，第 2 轮跳过，最早第 6 轮再检查。<br>
  **Name after the first turn**. Generate an initial title from the request and answer without requiring a topic change. Later checks are scheduled for turns 2, 6, 8, 10, …, subject to a 4-turn cooldown after every successful rename. A turn-1 rename skips turn 2; the next check is at turn 6.
- **补正失准的初始标题**。 尚未成功自动命名时，后续检查可以修正以会话链接、无意义开场白等充当标题的情况，不要求先换题；原标题准确就保持。成功命名后，再次更新仍要求主要话题有实质变化且原标题已失准，简单追问和换措辞不触发改名。<br>
  **Correct inaccurate initial titles**. Before the first successful automatic rename, later checks may replace a misleading initial title, such as a conversation link or meaningless opening fragment, without requiring a topic change. Accurate titles stay. After successful naming, further updates still require a substantial topic change and an inaccurate title; follow-ups and stylistic rewording do not qualify.
- **每个对话单独记数**。 仅统计完成的真实用户主会话轮次，工具调用、子代理和自动续跑不计入；重启后继续，同一轮不重复处理。<br>
  **Track each chat separately**. Count completed human turns in the main conversation, excluding tool calls, subagents and automatic continuations. State survives restarts; duplicate events are ignored.
- **可以固定标题**。 默认首次接管已有标题，此后检测到外部改名便暂停该对话的自动更新；首次遇到的手动标题无法自动识别，保护方法见下方技术说明。<br>
  **You can keep a title fixed**. Existing titles are adopted on first observation; a later external rename pauses updates for that chat. Pre-existing manual titles cannot be identified automatically; see the protection options below.

## 日常操作，直接告诉 Codex / Everyday prompts

| 想做什么 / Goal | 中文提示词 / Chinese prompt | English prompt |
| --- | --- | --- |
| 更新 / Update | 更新已安装的 Codex Title Updater，保留设置、状态和其他 Hook，并验证第一轮命名。 | Update the installed Codex Title Updater, preserving settings, state and other hooks, and verify first-turn naming. |
| 检查 / Check | 检查 Codex Title Updater 是否就绪，告诉我最近一次为什么保留或修改标题。 | Check whether Codex Title Updater is ready and explain its latest title decision. |
| 固定 / Lock | 用 Codex Title Updater 锁定当前对话标题。 | Lock this chat's title with Codex Title Updater. |
| 停用 / Pause | 停用 Codex Title Updater，保留设置和会话状态。 | Disable Codex Title Updater and keep its settings and state. |
| 恢复 / Resume | 重新启用 Codex Title Updater，并检查信任状态。 | Re-enable Codex Title Updater and check its trust status. |
| 卸载 / Uninstall | 卸载 Codex Title Updater，保留状态和备份，不影响其他 Hook。 | Uninstall Codex Title Updater, retaining state and backups and preserving other hooks. |

<details>
<summary>手动安装、命令行操作与技术说明 / Manual installation, CLI controls & technical details</summary>

## 手动安装与启用 / Manual install & enable

无第三方 Python 依赖。macOS 完整流程验证使用的 Codex 内核为 `0.163.0-alpha.10.2`；自动化测试覆盖 macOS、Ubuntu 和 Python 3.11、3.14。<br>
No third-party Python packages. The full macOS workflow was verified with Codex core `0.163.0-alpha.10.2`; automated tests cover macOS, Ubuntu, and Python 3.11/3.14.

```bash
git clone https://github.com/ye-kaifan/codex-title-updater.git
cd codex-title-updater
bash run_manage.sh install
```

已安装时，在仓库目录运行 `git pull --ff-only` 后重新执行 `bash run_manage.sh install` 即可更新。<br>
To update, run `git pull --ff-only` in the checkout, then rerun `bash run_manage.sh install`.

安装器合并 `~/.codex/hooks.json`，修改前备份；保留其他 Hook、`config.toml` 和 `notify`。重复安装不会重复注册，也不会覆盖设置和会话状态。设置了 `CODEX_HOME` 时使用该目录。<br>
The installer merges and backs up `~/.codex/hooks.json`, preserving other hooks, `config.toml` and `notify`. Reinstalling preserves settings/state and does not duplicate registration. `CODEX_HOME` is respected.

在与桌面端使用相同内核的 Codex CLI 中打开 `/hooks`，审核并信任命令包含 `codex-title-updater/title_updater.py hook` 的 `Stop` 项，然后重新打开对话。安装本身不会授予信任；步骤见 [官方 Hook 文档](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks)。<br>
Open `/hooks` in the Codex CLI matching your desktop core. Review and trust the `Stop` entry containing `codex-title-updater/title_updater.py hook`, then reopen the conversation. Installation does not grant trust; see the [official hook guide](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks).

若终端里的 Codex 比桌面内核旧，可使用桌面附带的 CLI，例如：<br>
If the terminal CLI is older than your desktop core, use the bundled CLI, for example:

```bash
/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex --no-daemon
```

## 验证 / Verify

```bash
bash run_tests.sh                          # 离线测试 / Offline tests
bash run_manage.sh status                  # 安装设置 / Installed settings
python3 ~/.codex/hooks/codex-title-updater/title_updater.py doctor
tail -n 20 ~/.codex/hooks/codex-title-updater/data/audit.jsonl
```

`doctor` 中对应 Hook 应唯一、启用且 `trustStatus: trusted`。测试对话完成第 1 轮后，日志应出现带 `initial_naming: true` 的 `check`，随后为 `keep` 或 `renamed`。第一轮成功改名后，第 2 轮为 `cooldown`，第 6 轮再检查；第 4 轮不检查。成功更新后的冷却轮次记录为 `cooldown`。手动改标题后再完成一轮，应出现 `manual_lock`。<br>
In `doctor`, the hook should appear once, enabled, with `trustStatus: trusted`. After turn 1 in a test conversation, expect `check` with `initial_naming: true`, followed by `keep` or `renamed`. A successful turn-1 rename logs `cooldown` at turn 2 and checks again at turn 6; no check at turn 4. A cooling-down turn logs `cooldown`. Manually editing a title, then completing another turn, should log `manual_lock`.

如果首轮命名被跳过或旧版本保留了失准的原标题，后续检查会记录 `initial_correction: true`。这允许校正初始标题，但仍须确认原标题确实失准；成功更新后恢复通常的换题要求。<br>
If first-turn naming was missed or an older version kept an inaccurate initial title, later checks log `initial_correction: true`. This permits correction only when the old title is inaccurate; normal topic-change requirements resume after a successful rename.

## 控制与配置 / Controls & settings

```bash
bash run_manage.sh disable                 # 停用 / Disable
bash run_manage.sh enable                  # 恢复 / Enable
bash run_manage.sh uninstall               # 移除自身注册，保留状态和备份 / Unregister; keep state & backups

# 用真实 thread_id 替换 THREAD_ID；可从 audit.jsonl 获取。
# Replace THREAD_ID with a real thread_id from audit.jsonl.
python3 ~/.codex/hooks/codex-title-updater/title_updater.py inspect THREAD_ID
python3 ~/.codex/hooks/codex-title-updater/title_updater.py lock THREAD_ID
python3 ~/.codex/hooks/codex-title-updater/title_updater.py unlock THREAD_ID
```

设置文件为 `~/.codex/hooks/codex-title-updater/settings.json`：`model: null` 使用 Codex 默认配置的模型，检查时默认使用 `reasoning_effort: "low"`；`adopt_existing: false` 可保护首次遇到的已有标题。`unlock` 接管当前标题，但保留四轮间隔。需要固定标题时，先 `lock` 再修改。<br>
Edit `~/.codex/hooks/codex-title-updater/settings.json`: `model: null` uses the default model in your Codex configuration, with `reasoning_effort: "low"` for reviews; `adopt_existing: false` protects titles already present on first observation. `unlock` adopts the current title without resetting the cooldown. For a fixed title, `lock` before editing.

`CODEX_TITLE_UPDATER_PYTHON` 可指定脚本使用的 Python；`CODEX_TITLE_UPDATER_CLI` 可指定 Codex 可执行文件；`CODEX_TITLE_UPDATER_HOME` 可指定状态目录。后两项需在运行 Hook 的 Codex 进程环境中设置。<br>
Use `CODEX_TITLE_UPDATER_PYTHON` to choose Python, `CODEX_TITLE_UPDATER_CLI` to choose the Codex executable, and `CODEX_TITLE_UPDATER_HOME` to relocate state. The latter two must be set in the Codex process running the hook.

## 数据与限制 / Data & limitations

- 检查调用当前配置的模型服务，使用登录额度或 API 计费。发送原标题和最近最多 8 个真实用户轮次的用户文本与最终回答，每段最多 1800 字符，不含工具输出。同步检查可能增加等待时间，模型超时为 90 秒。<br>
  Checks use your configured model provider and consume quota or incur API charges. Input includes the old title plus user text and final answers from up to 8 recent human turns, capped at 1,800 characters per message; tool output is excluded. Synchronous checks add latency; model timeout is 90 seconds.
- 状态和审计日志保存在安装目录的 `data/` 下，包含标题、轮次和判断摘要，不存对话全文；临时模型输入在结束后清理。请勿公开这些文件。<br>
  Local `data/` contains titles, turn state and audit summaries, not full transcripts. Temporary review inputs are cleaned up afterward. Keep state and logs private.
- 使用官方 [App Server](https://learn.chatgpt.com/docs/app-server) 的 `thread/read`、`thread/name/set` 并读回验证，不直接写数据库或对话文件。侧栏刷新取决于客户端。接口无法识别手动标题来源，也无原子比较后写入，极短的并发修改窗口仍存在。<br>
  Uses official [App Server](https://learn.chatgpt.com/docs/app-server) `thread/read` and `thread/name/set`, with read-back verification; no direct database/transcript writes. Sidebar refresh depends on the client. Title provenance and atomic compare-and-set are unavailable, leaving a small concurrent-edit race.
- 轮次计数依赖本地 transcript 的 `composer` 来源标记；格式未知时跳过。模型判断并非准确率保证；异常时保持标题，不触发原对话续跑。升级 Codex 后请重新验证。<br>
  Counting depends on local transcript `composer` attribution; unknown formats are skipped. Model judgments are not an accuracy guarantee. Errors preserve the title without continuing the original conversation. Recheck after Codex upgrades.

</details>

[MIT License](LICENSE) · 独立社区项目，与 OpenAI 无隶属关系。 / Independent community project; not affiliated with OpenAI.
