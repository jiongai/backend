# 🔐 GitHub 身份验证指南

## 问题：未能对 git remote 进行身份验证

GitHub 已停止支持密码认证（自 2021 年 8 月 13 日起），现在需要使用 **Personal Access Token (PAT)** 或 **SSH 密钥**。

---

## ✅ 解决方案 1：使用 Personal Access Token（推荐）

### 步骤 1：创建 GitHub Personal Access Token

1. **访问 GitHub 设置**：
   - 点击你的头像 → Settings
   - 或直接访问：https://github.com/settings/tokens

2. **生成新 Token**：
   - 左侧菜单：Developer settings → Personal access tokens → **Tokens (classic)**
   - 点击 **"Generate new token"** → **"Generate new token (classic)"**

3. **配置 Token**：
   - **Note（备注）**: 填写 `AudioDrama Backend` 或任何你记得住的名字
   - **Expiration（过期时间）**: 选择 `90 days` 或 `No expiration`
   - **Select scopes（权限）**: 勾选 `repo`（完整仓库访问权限）
     - ☑️ **repo** (Full control of private repositories)
       - ☑️ repo:status
       - ☑️ repo_deployment
       - ☑️ public_repo
       - ☑️ repo:invite
       - ☑️ security_events

4. **生成并复制 Token**：
   - 点击底部的 **"Generate token"**
   - **立即复制这个 Token**（只会显示一次！）
   - 格式类似：`ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

### 步骤 2：使用 Token 推送代码

在终端中执行：

```bash
cd /Users/baojiong/Documents/AI/AudioDrama/backend

# 添加所有更改
git add .

# 提交
git commit -m "Add Railway deployment config"

# 推送（会提示输入用户名和密码）
git push origin main
```

**当提示输入凭证时**：
- **Username**: 输入你的 GitHub 用户名（`jiongai`）
- **Password**: **粘贴刚才复制的 Personal Access Token**（不是你的 GitHub 密码！）

### 步骤 3：保存凭证（避免每次都输入）

推送成功后，保存凭证：

```bash
# macOS 使用 Keychain 保存
git config --global credential.helper osxkeychain

# 下次推送时会自动使用保存的凭证
```

---

## ✅ 解决方案 2：切换到 SSH（长期方案）

### 步骤 1：生成 SSH 密钥

```bash
# 生成新的 SSH 密钥
ssh-keygen -t ed25519 -C "your_email@example.com"

# 按提示操作：
# - 文件位置：直接按回车（使用默认 ~/.ssh/id_ed25519）
# - 密码：可以留空或设置密码
```

### 步骤 2：添加 SSH 密钥到 ssh-agent

```bash
# 启动 ssh-agent
eval "$(ssh-agent -s)"

# 添加 SSH 密钥
ssh-add ~/.ssh/id_ed25519
```

### 步骤 3：添加公钥到 GitHub

```bash
# 复制公钥到剪贴板
pbcopy < ~/.ssh/id_ed25519.pub
```

然后在 GitHub 上：

1. 访问：https://github.com/settings/keys
2. 点击 **"New SSH key"**
3. **Title**: 填写 `MacBook Pro` 或任何你记得住的名字
4. **Key**: 粘贴刚才复制的公钥
5. 点击 **"Add SSH key"**

### 步骤 4：切换远程仓库 URL

```bash
cd /Users/baojiong/Documents/AI/AudioDrama/backend

# 从 HTTPS 切换到 SSH
git remote set-url origin git@github.com:jiongai/backend.git

# 验证
git remote -v
# 应该显示：
# origin  git@github.com:jiongai/backend.git (fetch)
# origin  git@github.com:jiongai/backend.git (push)
```

### 步骤 5：测试 SSH 连接

```bash
ssh -T git@github.com
# 期望输出：
# Hi jiongai! You've successfully authenticated, but GitHub does not provide shell access.
```

### 步骤 6：推送代码

```bash
git push origin main
# 不再需要输入用户名和密码！
```

---

## 🆚 两种方案对比

| 特性 | Personal Access Token | SSH 密钥 |
|------|----------------------|----------|
| **设置难度** | ⭐⭐ 简单 | ⭐⭐⭐ 中等 |
| **设置时间** | 2 分钟 | 5 分钟 |
| **安全性** | ✅ 高 | ✅ 非常高 |
| **过期** | ⚠️ 可能过期 | ✅ 不过期 |
| **推荐场景** | 快速开始 | 长期使用 |

---

## 🔧 故障排除

### 1. Token 无效

**症状**：
```
remote: Invalid username or password.
fatal: Authentication failed
```

**解决**：
- 检查 Token 是否正确复制（包括 `ghp_` 前缀）
- 检查 Token 权限是否包含 `repo`
- Token 可能已过期，重新生成一个

### 2. SSH 密钥无法添加

**症状**：
```
Could not open a connection to your authentication agent.
```

**解决**：
```bash
# 启动 ssh-agent
eval "$(ssh-agent -s)"

# 然后重试
ssh-add ~/.ssh/id_ed25519
```

### 3. SSH 连接超时

**症状**：
```
ssh: connect to host github.com port 22: Operation timed out
```

**解决**：可能是网络问题，尝试使用 HTTPS + Token 方式。

---

## 📋 快速参考

### Personal Access Token 方式

```bash
# 1. 创建 Token：https://github.com/settings/tokens
# 2. 推送时使用 Token 作为密码
git push origin main
# Username: jiongai
# Password: <粘贴你的 Token>

# 3. 保存凭证
git config --global credential.helper osxkeychain
```

### SSH 方式

```bash
# 1. 生成密钥
ssh-keygen -t ed25519 -C "your_email@example.com"

# 2. 添加到 GitHub：https://github.com/settings/keys
pbcopy < ~/.ssh/id_ed25519.pub

# 3. 切换到 SSH URL
git remote set-url origin git@github.com:jiongai/backend.git

# 4. 推送
git push origin main
```

---

## ✅ 推荐方案

**如果你想快速部署到 Railway**：
1. 使用 **Personal Access Token** 方式（5 分钟搞定）
2. 先完成 Railway 部署
3. 之后有时间再配置 SSH 密钥

**如果你是长期开发**：
1. 直接配置 **SSH 密钥**（一劳永逸）
2. 更安全，不会过期

---

## 🎯 现在就开始

选择一个方案，按照步骤操作即可！

**需要帮助？** 看下面的常见问题或告诉我你遇到的具体错误信息。

