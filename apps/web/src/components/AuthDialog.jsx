import { useEffect, useRef, useState } from "react";

export function AuthDialog({ user, onClose, onLogin, onRegister, onLogout, onOpenAccess }) {
  const [mode, setMode] = useState(user ? "account" : "login");
  const [form, setForm] = useState({
    phone: "",
    displayName: "",
    password: "",
    passwordConfirm: "",
  });
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const firstFieldRef = useRef(null);

  useEffect(() => {
    firstFieldRef.current?.focus();
    const onKeyDown = (event) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [mode, onClose]);

  const updateField = (field) => (event) => {
    setForm((current) => ({ ...current, [field]: event.target.value }));
    setError("");
  };

  const submit = async (event) => {
    event.preventDefault();
    if (mode === "register" && form.password !== form.passwordConfirm) {
      setError("两次输入的密码不一致");
      return;
    }
    setIsSubmitting(true);
    setError("");
    try {
      if (mode === "register") {
        await onRegister({
          phone: form.phone,
          display_name: form.displayName,
          password: form.password,
          password_confirm: form.passwordConfirm,
        });
      } else {
        await onLogin({ phone: form.phone, password: form.password });
      }
      onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "操作失败，请稍后重试");
    } finally {
      setIsSubmitting(false);
    }
  };

  const signOut = async () => {
    setIsSubmitting(true);
    try {
      await onLogout();
      onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "退出失败，请稍后重试");
      setIsSubmitting(false);
    }
  };

  const switchMode = (nextMode) => {
    setMode(nextMode);
    setError("");
  };

  return (
    <div className="dialog-backdrop" onMouseDown={onClose}>
      <section
        className="dialog auth-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="auth-dialog-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <button ref={mode === "account" ? firstFieldRef : undefined} className="dialog-close" onClick={onClose} aria-label="关闭">×</button>
        {mode === "account" && user ? (
          <AccountView
            user={user}
            error={error}
            isSubmitting={isSubmitting}
            onLogout={signOut}
            onOpenAccess={onOpenAccess}
          />
        ) : (
          <>
            <img className="dialog-brand" src="/brand/jinghu-logo-lockup.png" alt="鲸互AI" />
            <div className="auth-heading">
              <p>{mode === "register" ? "创建你的创作空间" : "继续你的创作"}</p>
              <h2 id="auth-dialog-title">{mode === "register" ? "注册鲸互AI" : "登录鲸互AI"}</h2>
            </div>
            <form className="auth-form" onSubmit={submit}>
              {mode === "register" && (
                <label>
                  <span>昵称</span>
                  <input
                    ref={firstFieldRef}
                    value={form.displayName}
                    onChange={updateField("displayName")}
                    autoComplete="name"
                    minLength={1}
                    maxLength={80}
                    placeholder="怎么称呼你"
                    required
                  />
                </label>
              )}
              <label>
                <span>手机号</span>
                <input
                  ref={mode === "login" ? firstFieldRef : undefined}
                  value={form.phone}
                  onChange={updateField("phone")}
                  type="tel"
                  inputMode="tel"
                  autoComplete="tel"
                  placeholder="请输入手机号"
                  required
                />
              </label>
              <label>
                <span>密码</span>
                <input
                  value={form.password}
                  onChange={updateField("password")}
                  type="password"
                  autoComplete={mode === "register" ? "new-password" : "current-password"}
                  minLength={mode === "register" ? 8 : 1}
                  maxLength={128}
                  placeholder={mode === "register" ? "至少 8 位" : "请输入密码"}
                  required
                />
              </label>
              {mode === "register" && (
                <label>
                  <span>确认密码</span>
                  <input
                    value={form.passwordConfirm}
                    onChange={updateField("passwordConfirm")}
                    type="password"
                    autoComplete="new-password"
                    minLength={8}
                    maxLength={128}
                    placeholder="再次输入密码"
                    required
                  />
                </label>
              )}
              {error && <p className="auth-error" role="alert">{error}</p>}
              <button className="dialog-primary auth-submit" type="submit" disabled={isSubmitting}>
                {isSubmitting ? "请稍候…" : mode === "register" ? "注册并登录" : "登录"}
              </button>
            </form>
            <p className="auth-switch">
              {mode === "register" ? "已经有账号？" : "还没有账号？"}
              <button type="button" onClick={() => switchMode(mode === "register" ? "login" : "register")}>
                {mode === "register" ? "去登录" : "立即注册"}
              </button>
            </p>
            <p className="auth-terms">继续即表示你同意用户协议与隐私政策</p>
          </>
        )}
      </section>
    </div>
  );
}

function AccountView({ user, error, isSubmitting, onLogout, onOpenAccess }) {
  const canManageAccess = user.permissions.includes("*") || user.permissions.includes("access:manage");
  return (
    <div className="account-view">
      <div className="account-avatar" aria-hidden="true">{user.display_name.slice(0, 1)}</div>
      <p className="account-kicker">当前账号</p>
      <h2 id="auth-dialog-title">{user.display_name}</h2>
      <p className="account-phone">{user.phone}</p>
      <span className="account-role">{user.role.name}</span>
      {error && <p className="auth-error" role="alert">{error}</p>}
      <div className="account-actions">
        {canManageAccess && (
          <button className="dialog-primary" onClick={onOpenAccess}>权限配置</button>
        )}
        <button onClick={onLogout} disabled={isSubmitting}>
          {isSubmitting ? "正在退出…" : "退出登录"}
        </button>
      </div>
    </div>
  );
}
