# Codex Title Updater

让标题跟上内容，只在确有需要时更新。<br>
Keep titles in sync with the conversation—update only when it matters.

一个保守的 Codex `Stop` Hook：主要话题变化、原标题已不准确时，自动更新为简洁中文标题，保留必要的项目名和技术词。<br>
A conservative Codex `Stop` hook that updates an outdated title only after a meaningful topic change. Titles are concise Chinese, preserving project names and technical terms.

## 规则 / Behavior

| 中文 | English |
| --- | --- |
| 第 2 轮首次检查；此后在第 6、8、10…轮检查。 | Check after turn 2, then turns 6, 8, 10, … |
| 每次成功更新后，至少间隔 4 轮；保持原标题不重置间隔。 | Wait at least 4 turns after each successful update. Keeping a title does not reset the interval. |
| 同一任务的继续实现、排错、测试、润色和短暂插问不触发换标题。 | Follow-ups, debugging, testing, polishing and brief asides keep the current title. |
| 仅统计完成的真实用户主会话轮次；工具调用、子代理和自动续跑不计入。 | Count completed human turns in the main conversation; exclude tools, subagents and automatic continuations. |
| 各会话独立持久化；去重、进程锁和写入日志防止重复更新。 | Persist state per conversation, with deduplication, locking and a write journal. |
| 首次自动接管已有标题；此后检测到外部标题变化便锁定，直到手动解锁。 | Adopt existing titles on first observation; later external title changes lock the conversation until explicitly unlocked. |

## 安装与启用 / Install & enable

需要 **Python 3.11+**，无第三方 Python 依赖；Codex 须已登录，并支持原生 Hooks 与 App Server。macOS 已验证，内核版本为 `0.163.0-alpha.10.2`；Linux 尚未验证完整生命周期，Windows 暂不支持。<br>
Requires **Python 3.11+**, no third-party Python packages, and a signed-in Codex with native Hooks and App Server. Verified on macOS with core `0.163.0-alpha.10.2`; full lifecycle on Linux is unverified. Windows is not supported yet.

```bash
git clone https://github.com/ye-kaifan/codex-title-updater.git
cd codex-title-updater
bash run_manage.sh install
```

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

`doctor` 中对应 Hook 应唯一、启用且 `trustStatus: trusted`。测试对话完成第 2 轮后，日志应出现 `check`，随后为 `keep` 或 `renamed`；第 4 轮不检查。成功更新后的冷却轮次记录为 `cooldown`。手动改标题后再完成一轮，应出现 `manual_lock`。<br>
In `doctor`, the hook should appear once, enabled, with `trustStatus: trusted`. After turn 2 in a test conversation, expect `check` followed by `keep` or `renamed`; no check at turn 4. A cooling-down turn logs `cooldown`. Manually editing a title, then completing another turn, should log `manual_lock`.

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

设置文件为 `~/.codex/hooks/codex-title-updater/settings.json`：`model: null` 使用当前 Codex 配置，`adopt_existing: false` 可保护首次遇到的已有标题。`unlock` 接管当前标题，但保留四轮间隔。需要固定标题时，先 `lock` 再修改。<br>
Edit `~/.codex/hooks/codex-title-updater/settings.json`: `model: null` inherits Codex settings; `adopt_existing: false` protects titles already present on first observation. `unlock` adopts the current title without resetting the cooldown. For a fixed title, `lock` before editing.

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

[MIT License](LICENSE) · 独立社区项目，与 OpenAI 无隶属关系。 / Independent community project; not affiliated with OpenAI.
