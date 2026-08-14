# 有道云笔记自动签到

使用 GitHub Actions 每日定时执行有道云笔记签到，支持多账户，并可通过 PushDeer 推送汇总结果。

> 本项目调用有道云笔记当前网页端接口。该接口不是公开 API，将来可能因网页改版而失效。

## 功能

- GitHub Actions 每日定时运行，也支持手动触发
- 一个 Secret 配置多个有道云笔记账户
- 汇总每个账户的成功、已签到或失败状态
- 可选 PushDeer Markdown 推送
- Cookie、PushDeer Key 均通过 GitHub Actions Secrets 保存
- 日志不会输出 Cookie、PushDeer Key 或完整响应内容

## 一、获取有道云笔记 Cookie

1. 使用浏览器登录 [有道云笔记网页版](https://note.youdao.com/web/)。
2. 按 `F12` 打开开发者工具，选择 `Network`（网络）。
3. 刷新有道云笔记页面。
4. 在请求列表中选择一个发送到 `note.youdao.com` 的请求。
5. 在 `Request Headers`（请求标头）中找到 `Cookie`，复制其完整值。

Cookie 中必须包含 `YNOTE_CSTK`，通常还会包含 `YNOTE_SESS`、`YNOTE_PERS`、`YNOTE_LOGIN` 等字段。程序既接受纯 Cookie 值，也接受带 `Cookie:` 前缀的内容。

不要从开发者工具中只复制某一个 Cookie，也不要把 Cookie 写进 README、代码、Issue 或 Actions 普通变量。Cookie 相当于登录凭证，泄露后应退出登录或重新登录，使旧 Cookie 失效。

## 二、准备多账户 JSON

`YOUDAO_ACCOUNTS` 必须是 JSON 数组。每个元素包含：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `name` | 是 | 仅用于签到报告中区分账户，不参与登录 |
| `cookie` | 是 | 从该账户浏览器会话复制的完整 Cookie |

单账户示例：

```json
[
  {
    "name": "主账号",
    "cookie": "YNOTE_SESS=替换为真实值; YNOTE_CSTK=替换为真实值; YNOTE_LOGIN=替换为真实值"
  }
]
```

多账户示例：

```json
[
  {
    "name": "主账号",
    "cookie": "主账号的完整 Cookie"
  },
  {
    "name": "备用账号",
    "cookie": "备用账号的完整 Cookie"
  }
]
```

JSON 必须使用英文双引号，元素之间需要逗号。GitHub Secret 支持直接粘贴多行 JSON，无需压缩成一行。

## 三、配置 GitHub Actions Secrets

打开该 GitHub 仓库，然后进入：

`Settings` → `Secrets and variables` → `Actions` → `Secrets` → `New repository secret`

请配置以下 Repository secrets：

### 必填：`YOUDAO_ACCOUNTS`

- Name：`YOUDAO_ACCOUNTS`
- Secret：粘贴上一节准备好的完整 JSON 数组

注意 Secret 名称区分字符，必须与上面完全一致。不要把它放在 `Variables` 页签；普通 Variables 不适合保存敏感信息。

### 可选：`PUSHDEER_KEY`

- Name：`PUSHDEER_KEY`
- Secret：填写 PushDeer 设备对应的 Push Key，例如 `PDU...`

没有配置此 Secret 时，签到仍会执行，只会在日志中显示“跳过推送”。PushDeer Key 可从 PushDeer 客户端或管理页面获取。

配置完成后，工作流通过以下表达式读取 Secret：

```yaml
env:
  YOUDAO_ACCOUNTS: ${{ secrets.YOUDAO_ACCOUNTS }}
  PUSHDEER_KEY: ${{ secrets.PUSHDEER_KEY }}
```

## 四、启用并手动测试工作流

1. 打开仓库的 `Actions` 页面。
2. 如果 GitHub 显示工作流尚未启用，点击启用。
3. 在左侧选择 `Youdao Note Check-in`。
4. 点击 `Run workflow`，选择默认分支后再次确认。
5. 打开本次运行记录，检查 `Run check-in` 步骤。

正常输出示例：

```text
## 有道云笔记签到结果

账户数：2
成功：1，已签到：1，失败：0

✅ 主账号：签到成功，获得 2 MB
ℹ️ 备用账号：今日已签到
PushDeer：推送成功
```

只要任一账户签到失败，工作流就会以失败状态结束；其他账户仍会继续执行，PushDeer 也会收到汇总结果。

## 五、定时运行时间

工作流文件位于 `.github/workflows/checkin.yml`，默认配置为：

```yaml
schedule:
  - cron: "17 0 * * *"
```

GitHub Actions cron 使用 UTC。上面的时间表示每天 UTC 00:17，即北京时间 UTC+8 的 08:17。GitHub 定时任务可能因平台负载延迟几分钟。

如需改为北京时间 09:30，应换算为 UTC 01:30：

```yaml
schedule:
  - cron: "30 1 * * *"
```

修改工作流后提交到默认分支才会生效。私有仓库还需确保 GitHub Actions 可用且账户有足够的 Actions 使用额度。

## 六、本地测试（PowerShell）

需要 Python 3.10 或更高版本。在项目目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
```

推荐通过 `Read-Host` 输入 Cookie，避免直接写进 PowerShell 历史：

```powershell
$cookie = Read-Host "请输入有道云笔记 Cookie"
$accounts = @(
    @{
        name = "主账号"
        cookie = $cookie
    }
)

$env:YOUDAO_ACCOUNTS = ConvertTo-Json -InputObject $accounts -Compress
$env:PUSHDEER_KEY = Read-Host "请输入 PushDeer Key（不测试推送可直接回车）"
$env:YOUDAO_AD_REWARDS = "false"
$env:YOUDAO_DEBUG = "true"

python -m youdao_checkin.main
```

这里使用 `ConvertTo-Json -InputObject $accounts`，以确保只有一个账户时仍生成 JSON 数组。若不需要 PushDeer，可执行：

```powershell
Remove-Item Env:PUSHDEER_KEY -ErrorAction SilentlyContinue
```

测试结束后清理当前 PowerShell 会话中的敏感环境变量：

```powershell
Remove-Item Env:YOUDAO_ACCOUNTS -ErrorAction SilentlyContinue
Remove-Item Env:PUSHDEER_KEY -ErrorAction SilentlyContinue
Remove-Item Env:YOUDAO_DEBUG -ErrorAction SilentlyContinue
```

运行自动化测试：

```powershell
python -m pytest -q
```

## 七、全部配置参数

| 环境变量 | 必填 | 默认值 | 配置位置 | 说明 |
| --- | --- | --- | --- | --- |
| `YOUDAO_ACCOUNTS` | 是 | 无 | GitHub Repository Secret | 账户 JSON 数组 |
| `PUSHDEER_KEY` | 否 | 无 | GitHub Repository Secret | PushDeer Push Key；为空时跳过通知 |
| `YOUDAO_DEVICE_TYPE` | 否 | `PC` | 工作流 `env` | 可选值为 `PC`、`Mac`、`Linux`；工作流当前设为 `Linux` |
| `YOUDAO_AD_REWARDS` | 否 | `false` | 工作流 `env` | 是否尝试领取额外广告奖励；建议保持关闭 |
| `YOUDAO_TIMEOUT` | 否 | `20` | 工作流 `env` | HTTP 请求超时秒数，必须大于 0 |
| `PUSHDEER_ENDPOINT` | 否 | `https://api2.pushdeer.com/message/push` | 工作流 `env` | 自建 PushDeer 服务时替换接口地址 |
| `YOUDAO_DEBUG` | 否 | 关闭 | 临时调试环境变量 | 输出不含敏感值的请求诊断信息 |

`YOUDAO_DEVICE_TYPE` 和 `YOUDAO_AD_REWARDS` 已在 `.github/workflows/checkin.yml` 中设置。普通非敏感参数也可以放在 GitHub 的 `Actions variables`，但若这样做，需要把工作流对应值改为 `${{ vars.变量名 }}`。

## 八、常见问题

### 提示“登录态失效，请更新 Cookie”

- 确认复制的是当前已登录 `note.youdao.com` 页面请求中的完整 Cookie。
- 确认 Cookie 包含 `YNOTE_CSTK`。
- 重新登录有道云笔记后再次复制，并更新 `YOUDAO_ACCOUNTS` Secret。
- 更新 Secret 后手动运行一次工作流验证。

### 提示 `YOUDAO_ACCOUNTS 必须是非空账户数组`

检查 Secret 最外层是否为 `[` 和 `]`，并确认 JSON 使用英文双引号。可以先在本地用 PowerShell 的 `ConvertFrom-Json` 检查结构，但不要把真实内容提交到在线 JSON 校验网站。

### 本地显示“未配置 PUSHDEER_KEY”

说明当前 PowerShell 会话没有该环境变量。这不影响签到；如需测试推送，请重新设置 `$env:PUSHDEER_KEY`。

### GitHub Actions 没有准时运行

定时任务不是实时调度，平台繁忙时可能延迟。还应确认工作流存在于默认分支、Actions 已启用，并且仓库近期没有因长期无活动而暂停计划任务。

## 安全说明

- 不要提交 `.env`、Cookie、Actions 日志副本或 PushDeer Key。
- 本项目的 `.gitignore` 已忽略 `.env`、虚拟环境、缓存和构建产物。
- GitHub Secrets 保存后无法再次查看原值，只能覆盖更新。
- Cookie 失效属于正常现象，更新 Secret 即可，无需修改代码。
- 若 Cookie 或 PushDeer Key 曾粘贴到聊天、Issue、代码或其他公开位置，请立即轮换。

## 项目结构

```text
.github/workflows/checkin.yml  GitHub Actions 定时任务
src/youdao_checkin/config.py   环境变量和多账户配置
src/youdao_checkin/client.py   有道网页端签到请求
src/youdao_checkin/notifier.py PushDeer 推送
src/youdao_checkin/main.py     多账户执行与结果汇总
tests/                         自动化测试
```

## 免责声明

本项目仅供个人学习和自动化自用。请遵守有道云笔记及 PushDeer 的服务条款，合理设置运行频率，并自行承担使用非公开网页接口可能产生的风险。
