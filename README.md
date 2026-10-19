# Codex Title Updater

[![Tests](https://github.com/ye-kaifan/codex-title-updater/actions/workflows/tests.yml/badge.svg)](https://github.com/ye-kaifan/codex-title-updater/actions/workflows/tests.yml)

**让 Codex 的标题跟上对话，回头找聊天更方便**。<br>
**Keep Codex titles relevant as your conversation evolves, so chats are easier to find**.

Codex 已有自动命名，但标题有时只留下会话链接或含糊的开场白，后来聊到正题也未能准确概括内容。Codex Title Updater 在自带标题基础上补充检查：原标题准确且长度合规就保留；超长标题由程序强制进入纠正流程，首轮明显失准时纠偏，后续主要话题变了再按需更新。更新后的标题使用简洁中文，保留项目名和技术词。<br>
Codex already generates titles, but a title may capture a conversation link or vague opening instead of the actual task. Codex Title Updater supplements built-in naming: keep accurate titles within the length limit, require repair of overlong titles, correct misleading initial titles, and update them when the main topic changes later. Updated titles use concise Chinese while preserving project names and technical terms.

它通过 Codex 的 `Stop` Hook 在一轮结束时触发。首轮也先检查标题是否准确、长度是否合规，不为换措辞而重新命名；尚未成功自动校正时，无需先发生话题变化，就可以补正失准的初始标题。<br>
It runs through Codex's `Stop` hook at the end of a turn. Even the first check preserves accurate titles within the length limit rather than rewording them. Until the first successful automatic correction, a misleading initial title can be fixed without a topic change.

## 选择安装或自行创建 / Install or build your own

想直接使用，选**方式一**，省去重新设计、开发和调试的过程；想自己实现一套、探索不同规则，选**方式二**。两种提示词都可以直接复制给 Codex。<br>
Choose **Option 1** to use this project and skip designing, developing, and debugging it again. Choose **Option 2** to build your own implementation and explore different rules. Both prompts are ready to paste into Codex.

### 方式一：安装现成项目 / Option 1: Install this project

适用于支持原生 Hooks 和 App Server 的已登录 Codex，需要 **Python 3.11+**。支持 macOS、Linux 和原生 Windows，Windows 无需 WSL。三平台均有离线测试、隔离安装流程和真实 App Server 接口检查；已登录环境中的完整 Hook 流程目前仅在 macOS 实测，Windows 和 Linux 仍需在实际客户端完成信任与对话验证。<br>
Requires a signed-in Codex with native Hooks and App Server, plus **Python 3.11+**. Supports macOS, Linux and native Windows without WSL. All three have offline tests, isolated installation checks and native App Server API checks. The signed-in end-to-end hook workflow has been manually verified on macOS; Windows and Linux still need trust review and conversation testing in a real client.

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

**安装后需在 `/hooks` 中审核并信任，才会运行**。 完成启用后，在新对话中完成一轮即可验证首轮检查；原标题准确且长度合规时，“保留”就是正确结果。<br>
**Review and trust the hook in `/hooks` before it can run**. Once enabled, complete one turn in a new conversation to verify the first check. Keeping an accurate title within the length limit is a successful result.

标题判断会调用你在 Codex 中配置的模型服务，消耗额度或产生 API 费用，也可能增加轮末等待时间。<br>
Title reviews use your configured Codex model provider, consume quota or incur API charges, and may add a wait at the end of a turn.

### 方式二：让 Codex 从头创建 / Option 2: Have Codex build it from scratch

下面给出创建一套独立 Hook 的需求；检查频率、标题语言和改名条件都可以先改成自己的偏好：<br>
Use the following requirements to create an independent hook. Adjust the review schedule, title language, and rename conditions to suit your preferences:

```text
请从头创建一个标题检查和更新 Hook，补充 Codex 自带的自动命名，方便查找历史会话。

规则：
- 第 1 轮对话完成后，结合实际需求和回答检查已有标题；准确且长度合规就保留，明显失准时纠正，不要求话题已变化。
- 如果错过首轮且尚未成功自动校正过标题，后续检查仍允许纠正失准的初始标题。
- 第 2 轮检查；从第 6 轮起，每 2 轮检查一次。每次成功改名后，至少间隔 4 轮再检查。因此首轮改名成功时跳过第 2 轮，下次在第 6 轮检查。
- 成功校正初始标题后，对长度合规的标题，只有主要话题发生变化、原标题已不准确时才再次修改，不为换措辞而改名。
- 超过字符上限的标题必须纠正，不因含义准确而保留，也不受换题、检查轮次或冷却期限制；仍尊重手动锁定。生成失败时记录待纠正，下一个真人轮次重试，不能截断凑数。
- 标题使用简洁中文，突出具体对象和核心任务，保留必要的项目名与技术词。
- 只统计真实用户主会话轮次，工具调用、子代理和自动续跑不计入；各会话独立计数，重启后保留状态。
- 尊重用户手动设置的标题；如果接口无法区分已有标题是手写还是自动生成，请说明处理方案。避免重复触发和循环改名。

先检查当前 Codex 实际支持的 Hook 和改名接口，再完成实现、安装与验证。保留已有配置和其他 Hook。
用测试对话验证准确标题保留、失准标题纠正，以及后续换题更新。
需要我手动审核信任时，请告诉我具体操作；完成后告诉我如何停用和恢复。
```

```text
Build a title-review and update hook from scratch to supplement Codex's built-in naming and make past chats easier to find.

Rules:
- After the first completed turn, review the existing title against the actual request and answer. Keep accurate titles within the length limit and correct clearly misleading ones; a topic change is not required.
- If the first check was missed and no automatic correction has succeeded yet, later checks may still correct an inaccurate initial title.
- Check at turn 2, then every two turns from turn 6 onward. After each successful rename, wait at least four turns before checking again. A turn-1 rename therefore skips turn 2 and checks again at turn 6.
- After the initial title has been corrected, rename a title within the length limit only when the main topic has substantially changed and the old title is inaccurate. Do not rename merely to rephrase it.
- Repair titles exceeding the character limit regardless of semantic accuracy, topic changes, schedule or cooldown; continue respecting manual locks. If generation fails, record a deferred repair and retry on the next human turn instead of truncating the title.
- Use concise Chinese titles that identify the specific subject and core task, preserving relevant project names and technical terms.
- Count only real human turns in the main conversation, excluding tool calls, subagents, and automatic continuations. Track each chat independently and preserve state across restarts.
- Respect manually set titles. If the interface cannot distinguish existing manual titles from generated ones, explain how they will be handled. Prevent duplicate processing and recursive renaming.

First check the hook and title-update interfaces actually supported by my Codex installation, then implement, install, and verify the hook. Preserve my existing configuration and other hooks.
Use test conversations to verify that accurate titles stay, misleading titles are corrected, and later topic changes trigger appropriate updates.
Guide me through any manual trust review, and explain how to disable and re-enable the hook.
```

以下功能、实测开销和操作说明针对本仓库的实现。<br>
The behavior, measured costs, and controls below describe this repository's implementation.

## 标题什么时候会改 / When titles change

- **第一轮先检查**。 首轮结束后，结合需求和回答检查现有标题，准确且长度合规就保留，明显失准时校正。常规检查点为第 2、6、8、10…轮；每次成功改名都需冷却至少 4 轮。首轮保留不触发冷却，第 2 轮仍会检查；首轮成功改名则最早第 6 轮再检查。<br>
  **Check after the first turn**. Review the existing title against the request and answer; keep it when accurate and within the length limit, and correct it when clearly misleading. Regular checks are scheduled for turns 2, 6, 8, 10, …, subject to a 4-turn cooldown after each successful rename. Keeping the title at turn 1 allows a turn-2 check; a turn-1 rename delays the next check until turn 6.
- **补正失准的初始标题**。 尚未成功自动命名时，后续检查可以修正以会话链接、无意义开场白等充当标题的情况，不要求先换题；原标题准确且长度合规就保持。成功命名后，长度合规标题的再次更新仍要求主要话题有实质变化且原标题已失准，简单追问和换措辞不触发改名。<br>
  **Correct inaccurate initial titles**. Before the first successful automatic rename, later checks may replace a misleading initial title, such as a conversation link or meaningless opening fragment, without requiring a topic change. Accurate titles within the length limit stay. After successful naming, updates to compliant titles still require a substantial topic change and an inaccurate title; follow-ups and stylistic rewording do not qualify.
- **超长标题必须纠正**。 `max_title_chars` 默认是 40，按 Python `len` 统计 Unicode 字符，包含空格、标点和英文字符。它同时约束旧标题和新标题；40 字符可保留，41 字符就进入独立纠正流程，即使含义准确、话题没变、未到常规检查点或仍在冷却期。模型只生成短标题，不再投票决定是否保留；人工锁定、外部改名保护及停用开关仍优先。<br>
  **Repair overlong titles**. `max_title_chars` defaults to 40 Unicode characters counted by Python `len`, including spaces, punctuation and Latin letters. It applies to both existing and replacement titles: 40 characters may stay; 41 triggers a separate repair even when accurate, on the same topic, outside the schedule or during cooldown. The model generates a replacement instead of deciding whether to keep the old title. Manual locks, external-edit protection and disablement still take precedence.
- **失败不冒充保留成功**。 超长纠正遇到超时、低置信度或非法结果，记录 `repair_deferred` 和原因，不会记录为 `keep`，也不会直接截断。每个真人轮次至多调用模型一次，同一事件不重复处理；下一个真人轮次仍超长时继续纠正。成功后恢复常规检查与冷却。<br>
  **Distinguish failure from keeping a valid title**. Timeouts, low confidence or invalid repair results log `repair_deferred` with a cause, never `keep`, and never trigger blind truncation. At most one model call is made per human turn; duplicate events are ignored. The next human turn retries if the title is still overlong. Successful repair restores normal scheduling and cooldown.
- **每个对话单独记数**。 仅统计完成的真实用户主会话轮次，工具调用、子代理和自动续跑不计入；重启后继续，同一轮不重复处理。<br>
  **Track each chat separately**. Count completed human turns in the main conversation, excluding tool calls, subagents and automatic continuations. State survives restarts; duplicate events are ignored.
- **可以固定标题**。 默认首次接管已有标题，此后检测到外部改名便暂停该对话的自动更新；首次遇到的手动标题无法自动识别，保护方法见下方技术说明。<br>
  **You can keep a title fixed**. Existing titles are adopted on first observation; a later external rename pauses updates for that chat. Pre-existing manual titles cannot be identified automatically; see the protection options below.

## 运行开销 / Runtime cost

2026 年 10 月 17 日，用四个短对话样例实测了首轮纠偏、保留准确标题和后续换题检查：<br>
Four short synthetic cases tested first-turn correction, keeping an accurate title, and a later topic change on October 17, 2026:

| 标题检查配置 / Review configuration | 样例数 / Cases | 单次总 tokens / Total tokens per check |
| --- | ---: | ---: |
| GPT-6.1-Sol + xhigh | 3 | 17,366–17,494 |
| GPT-6-Astra + low（测试者当前 Hook 配置 / tester's current hook configuration） | 1 | 17,196 |

数据来自 CLI 返回的实际用量；总量为输入加输出，包含 CLI 构建的完整请求上下文。四次均以输入为主（17,112–17,208 tokens），输出为 84–320 tokens，返回的缓存输入均为 0。这是短样例的单次检查开销，不含开发或测试聊天本身的用量；实际消耗会随配置、对话长度及服务端缓存情况变化。<br>
These are CLI-reported usage figures: input plus output, including the full request context assembled by the CLI. Input dominated each call (17,112–17,208 tokens); output was 84–320 tokens, with zero cached input reported. These figures cover individual short-case reviews, excluding development or test-chat usage. Actual consumption varies with configuration, conversation length, and provider caching.

**跳过检查时，不产生标题判断的模型消耗；检查后决定保留标题，仍会消耗 tokens**。例如，标题长度合规且未到检查轮次或处于冷却期，或者标题已锁定时，都不会发出标题判断请求。<br>
**Skipped checks make no title-review model request; a completed check still consumes tokens even if the title stays unchanged**. Unscheduled turns and cooldowns skip reviews of length-compliant titles; locked titles always skip the request.

Hook 默认使用 Codex 配置中的默认模型，并单独设置 `low` 推理档位；主聊天选择 `xhigh` 不会让 Hook 自动跟着使用 `xhigh`。上表中的 Astra 是测试者的本机默认模型，并非项目固定指定的模型。测试通过自定义服务商运行，模型名称和档位按 CLI 生效配置记录。<br>
By default, the hook uses the default model in your Codex configuration and sets its own reasoning effort to `low`; choosing `xhigh` in the main chat does not change the hook's effort. Astra above was the tester's local default, not a model hardcoded by this project. Tests used a custom provider; model names and effort levels reflect the effective CLI configuration.

## 日常操作，直接告诉 Codex / Everyday prompts

| 想做什么 / Goal | 中文提示词 / Chinese prompt | English prompt |
| --- | --- | --- |
| 更新 / Update | 更新已安装的 Codex Title Updater，保留设置、状态和其他 Hook，并验证首轮检查：准确标题保留，失准标题校正。 | Update the installed Codex Title Updater, preserving settings, state and other hooks, and verify that the first check keeps accurate titles and corrects misleading ones. |
| 检查 / Check | 检查 Codex Title Updater 是否就绪，告诉我最近一次为什么保留或修改标题。 | Check whether Codex Title Updater is ready and explain its latest title decision. |
| 固定 / Lock | 用 Codex Title Updater 锁定当前对话标题。 | Lock this chat's title with Codex Title Updater. |
| 停用 / Pause | 停用 Codex Title Updater，保留设置和会话状态。 | Disable Codex Title Updater and keep its settings and state. |
| 恢复 / Resume | 重新启用 Codex Title Updater，并检查信任状态。 | Re-enable Codex Title Updater and check its trust status. |
| 卸载 / Uninstall | 卸载 Codex Title Updater，保留状态和备份，不影响其他 Hook。 | Uninstall Codex Title Updater, retaining state and backups and preserving other hooks. |

<details>
<summary>手动安装、命令行操作与技术说明 / Manual installation, CLI controls & technical details</summary>

## 手动安装与启用 / Manual install & enable

无第三方 Python 依赖。macOS 完整流程实测和三平台 CI 的原生接口检查均使用 Codex 内核 `0.163.0-alpha.10.2`；离线测试覆盖 macOS、Ubuntu、Windows 和 Python 3.11、3.12、3.14。可使用 Codex 内置的兼容 Python；不要求另装一套 Python。<br>
No third-party Python packages. Both the manual macOS workflow and native API checks in three-platform CI use Codex core `0.163.0-alpha.10.2`. Offline tests cover macOS, Ubuntu, Windows and Python 3.11/3.12/3.14. A compatible Python bundled with Codex can be used; a separate installation is not required.

macOS / Linux：

```bash
git clone https://github.com/ye-kaifan/codex-title-updater.git
cd codex-title-updater
bash run_manage.sh install
```

Windows（PowerShell，原生 Python 入口）/ Windows (PowerShell, native Python entry point):

```powershell
git clone https://github.com/ye-kaifan/codex-title-updater.git
cd codex-title-updater
python -X utf8 manage.py install
python -X utf8 manage.py status
python -X utf8 manage.py doctor
```

也可用 `py -3.12 -X utf8 manage.py install`，或 `& 'C:\完整路径\python.exe' -X utf8 .\manage.py install` 指定 Codex 内置 Python。仓库另有 `run_manage.ps1` 和 `run_tests.ps1`；设置 `$env:CODEX_TITLE_UPDATER_PYTHON` 为完整 Python 路径后即可使用。若本机策略不允许运行 `.ps1` 文件，直接使用上面的 Python 命令。<br>
Alternatively use `py -3.12 -X utf8 manage.py install`, or `& 'C:\full path\python.exe' -X utf8 .\manage.py install` for Codex's bundled Python. Optional `run_manage.ps1` and `run_tests.ps1` wrappers honor `$env:CODEX_TITLE_UPDATER_PYTHON` as a full Python path. If local policy blocks `.ps1` files, use the Python commands above.

已安装时，在仓库目录运行 `git pull --ff-only`，再重新执行对应平台的 `install` 命令即可更新。启动命令变化后可能需要重新审核信任。<br>
To update, run `git pull --ff-only` in the checkout and rerun your platform's `install` command. A changed launch command may require another trust review.

安装器合并 `~/.codex/hooks.json`（Windows 默认为 `%USERPROFILE%\.codex\hooks.json`），修改前备份；保留其他 Hook、`config.toml` 和 `notify`。重复安装不会重复注册，也不会覆盖设置、停用状态和会话状态。设置了 `CODEX_HOME` 时使用该目录，也可向 `manage.py` 传入 `--codex-home PATH` 和 `--install-dir PATH`。注册项明确绑定所选 `CODEX_HOME`；安装目录中的管理入口会记住所属目录。<br>
The installer merges and backs up `~/.codex/hooks.json` (`%USERPROFILE%\.codex\hooks.json` on Windows), preserving other hooks, `config.toml` and `notify`. Reinstalling preserves settings, disabled status and session state without duplicate registration. `CODEX_HOME` is respected; `manage.py` also accepts `--codex-home PATH` and `--install-dir PATH`. The hook registration binds the selected `CODEX_HOME`, and installed management entry points remember their installation location.

在与桌面端使用相同内核的 Codex CLI 中打开 `/hooks`，审核并信任状态说明为“检查会话标题”的 `Stop` 项，然后重新打开对话。macOS/Linux 命令包含 `title_updater.py hook`；Windows 使用编码后的 PowerShell 启动命令，以保护中文、空格及 `%`、`!`、`&` 等路径字符，并按 UTF-8 传递 Hook 输入。完整注册命令保存在安装目录的 `registration.json` 中。安装本身不会授予信任；步骤见 [官方 Hook 文档](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks)。<br>
Open `/hooks` in the Codex CLI matching your desktop core. Review and trust the `Stop` entry whose status message is “检查会话标题”, then reopen the conversation. macOS/Linux commands contain `title_updater.py hook`; Windows uses an encoded PowerShell launcher to protect Unicode, spaces and path characters such as `%`, `!` and `&`, forwarding hook input as UTF-8. The full registered command is saved in the installation's `registration.json`. Installation does not grant trust; see the [official hook guide](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks).

若终端里的 Codex 比桌面内核旧，可使用桌面附带的 CLI，例如：<br>
If the terminal CLI is older than your desktop core, use the bundled CLI, for example:

```bash
/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex --no-daemon
```

## 验证 / Verify

```bash
bash run_tests.sh                          # 离线测试 / Offline tests
bash run_manage.sh status                  # 安装设置 / Installed settings
bash run_manage.sh doctor                  # 原生接口与信任状态 / Native API & trust
tail -n 20 ~/.codex/hooks/codex-title-updater/data/audit.jsonl
```

```powershell
python -X utf8 -m unittest discover -s tests -v  # Windows 离线测试 / Offline tests
python -X utf8 manage.py status
python -X utf8 manage.py doctor
# CODEX_HOME 未设置时的默认日志位置 / Default log when CODEX_HOME is unset
Get-Content "$env:USERPROFILE\.codex\hooks\codex-title-updater\data\audit.jsonl" -Tail 20 -Encoding UTF8
```

验证分为三层，避免把 CI 结果当成已登录环境中的完整验证：<br>
Validation has three levels; CI results do not establish a signed-in end-to-end workflow:

| 层次 / Level | 已覆盖范围 / Coverage | 是否调用模型 / Model calls |
| --- | --- | --- |
| 离线测试 / Offline tests | 三平台的规则回归、跨进程锁、RPC 分片/通知/超时、阻塞输入、进程树清理、中文及特殊字符路径、安装/更新/启停/卸载 / Three-platform policy regression, process locks, fragmented RPC/notifications/timeouts, blocked stdin, process-tree cleanup, Unicode/special paths, installation/update/controls/uninstall | 否 / No |
| 原生接口检查 / Native API checks | 三平台真实 Codex 中的隔离安装、重复安装、`doctor`/`hooks/list`、虚构会话的创建与改名读回、配置保留 / Real Codex on all three platforms: isolated install/reinstall, `doctor`/`hooks/list`, synthetic thread creation/name-set/read, configuration preservation | 否 / No |
| 已登录客户端 / Signed-in client | `/hooks` 人工信任后，实际完成对话并检查审计日志；macOS 已实测，Windows/Linux 待实际环境验证 / Trust in `/hooks`, complete real turns and inspect audit logs; manually verified on macOS, pending on Windows/Linux | 是 / Yes |

CI 原生接口检查可在本机复现：`python -X utf8 run_native_checks.py --work-dir work/native --report work/native-report.json`。只使用临时 `CODEX_HOME` 和合成数据，不读取真实对话或登录文件，也不会自动授予信任。`run_live_checks.py` 是另一个会调用模型的合成样例检查工具，不属于离线 CI；它也不能替代客户端中的真实 Stop Hook 验证。<br>
Reproduce CI's native checks with `python -X utf8 run_native_checks.py --work-dir work/native --report work/native-report.json`. They use a temporary `CODEX_HOME` and synthetic data without reading real conversations/login files or granting trust. The separate `run_live_checks.py` submits synthetic cases to a model and is excluded from offline CI; it also does not replace real Stop-hook validation in a client.

`doctor` 中对应 Hook 应唯一、启用且 `trustStatus: trusted`。测试对话完成第 1 轮后，日志应出现带 `initial_naming: true` 的 `check`，随后为 `keep` 或 `renamed`。第一轮成功改名后，第 2 轮为 `cooldown`，第 6 轮再检查；第 4 轮不检查。成功更新后的冷却轮次记录为 `cooldown`。手动改标题后再完成一轮，应出现 `manual_lock`。<br>
In `doctor`, the hook should appear once, enabled, with `trustStatus: trusted`. After turn 1 in a test conversation, expect `check` with `initial_naming: true`, followed by `keep` or `renamed`. A successful turn-1 rename logs `cooldown` at turn 2 and checks again at turn 6; no check at turn 4. A cooling-down turn logs `cooldown`. Manually editing a title, then completing another turn, should log `manual_lock`.

超长标题检查还应有 `length_repair: true`、`title_chars` 和 `max_title_chars`。成功时为 `renamed`，生成失败时为 `repair_deferred`（`cause` 区分模型错误、置信度或标题校验失败）；普通改名建议未通过校验时为 `proposal_rejected`。`keep` 只表示长度合规标题的规则判定保留。<br>
Length checks also log `length_repair: true`, `title_chars` and `max_title_chars`. Success logs `renamed`; failed generation logs `repair_deferred`, with `cause` distinguishing model errors, confidence and title validation. Invalid regular rename proposals log `proposal_rejected`. `keep` means a policy decision to retain a length-compliant title.

升级后，旧版已经 `keep` 的超长标题会在下一个真人轮次结束时纠正。也可以对已停止且最后一轮已完成的聊天运行以下命令立即补正；只处理超长标题，沿用原轮次，不清除人工锁定，也不触发新对话轮次。重复执行时，已经合规的标题不会再次调用模型。<br>
After upgrading, an overlong title previously kept by an older version is repaired after the next human turn. To repair it immediately, use the following command on a stopped chat whose last turn completed. It only repairs overlong titles, preserves the original turn count and manual locks, and starts no conversation turn. Repeating it does not call the model once the title complies.

```bash
python3 ~/.codex/hooks/codex-title-updater/title_updater.py repair THREAD_ID
```

Windows 使用 `python -X utf8 "$env:USERPROFILE\.codex\hooks\codex-title-updater\title_updater.py" repair THREAD_ID`；设置了 `CODEX_HOME` 或自定义安装目录时替换路径。执行后用 `inspect` 或审计日志确认是 `renamed`、`repair_deferred`，还是仍受锁定保护。<br>
On Windows, use `python -X utf8 "$env:USERPROFILE\.codex\hooks\codex-title-updater\title_updater.py" repair THREAD_ID`; substitute a custom `CODEX_HOME` or installation path as needed. Inspect the state or audit log to confirm a rename, deferred repair, or preserved lock.


如果首轮命名被跳过或旧版本保留了失准的原标题，后续检查会记录 `initial_correction: true`。这允许校正初始标题，但仍须确认原标题确实失准；成功更新后恢复通常的换题要求。<br>
If first-turn naming was missed or an older version kept an inaccurate initial title, later checks log `initial_correction: true`. This permits semantic correction when the old title is inaccurate; normal topic-change requirements resume after a successful rename. Length repair remains independent.

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

Windows 使用 `python -X utf8 manage.py disable`、`enable`、`uninstall`。`inspect`、`lock`、`unlock` 使用安装后的 `title_updater.py`，例如：<br>
On Windows use `python -X utf8 manage.py disable`, `enable` or `uninstall`. Run `inspect`, `lock` and `unlock` against the installed `title_updater.py`, for example:

```powershell
# 若设置了 CODEX_HOME，请替换为该目录 / Substitute CODEX_HOME when set
python -X utf8 "$env:USERPROFILE\.codex\hooks\codex-title-updater\title_updater.py" lock THREAD_ID
```

设置文件为 `~/.codex/hooks/codex-title-updater/settings.json`：`model: null` 使用 Codex 默认配置的模型，检查时默认使用 `reasoning_effort: "low"`；`adopt_existing: false` 可保护首次遇到的已有标题。`unlock` 接管当前标题，但保留常规检查的四轮间隔；超长纠正不受该间隔限制。需要固定标题时，先 `lock` 再修改。<br>
Edit `~/.codex/hooks/codex-title-updater/settings.json`: `model: null` uses the default model in your Codex configuration, with `reasoning_effort: "low"` for reviews; `adopt_existing: false` protects titles already present on first observation. `unlock` adopts the current title without resetting the regular cooldown; length repair bypasses it. For a fixed title, `lock` before editing.

`CODEX_TITLE_UPDATER_PYTHON` 可为 `.sh`/`.ps1` 入口指定完整 Python 路径；直接运行 `manage.py` 时使用当前 Python，安装器将其写入注册命令。`CODEX_TITLE_UPDATER_CLI` 可指定完整 Codex 可执行文件路径，不含外层引号或额外参数；`CODEX_TITLE_UPDATER_HOME` 可指定状态目录。后两项需在运行 Hook 的 Codex 进程环境中设置。<br>
`CODEX_TITLE_UPDATER_PYTHON` selects a full Python path for `.sh`/`.ps1` wrappers; direct `manage.py` invocation registers the Python currently running it. `CODEX_TITLE_UPDATER_CLI` selects a full Codex executable path without surrounding quotes or extra arguments. `CODEX_TITLE_UPDATER_HOME` relocates state. The latter two must be set in the Codex process running the hook.

自动发现优先使用显式指定的 CLI，其次为 macOS 桌面内核和 `PATH`。Windows 的 npm `codex.cmd`/`codex.ps1` 会解析到相邻安装包中当前架构的原生 `codex.exe`，不通过 shell 转发模型参数；无法解析时请明确指定原生 `codex.exe`。Linux 需让 `codex` 在 `PATH` 中，或设置上述变量。显式路径无效时会报错，不会悄悄换用另一版本。<br>
Discovery prioritizes explicit CLI overrides, then macOS desktop cores and `PATH`. On Windows, npm `codex.cmd`/`codex.ps1` shims resolve to the adjacent package's native `codex.exe` for the current architecture, avoiding shell forwarding of model arguments. If resolution fails, specify the native `codex.exe` explicitly. On Linux, put `codex` on `PATH` or set the override. Invalid explicit paths fail instead of silently selecting another version.

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
