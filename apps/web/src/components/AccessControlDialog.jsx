import { useEffect, useRef, useState } from "react";
import {
  getAccessConfiguration,
  updateRolePermissions,
  updateUserAccess,
} from "../api/auth.js";

export function AccessControlDialog({ currentUser, onClose, onCurrentUserChange }) {
  const [config, setConfig] = useState(null);
  const [tab, setTab] = useState("users");
  const [error, setError] = useState("");
  const [savingId, setSavingId] = useState("");
  const closeRef = useRef(null);

  useEffect(() => {
    const controller = new AbortController();
    getAccessConfiguration(controller.signal)
      .then(setConfig)
      .catch((caught) => {
        if (!controller.signal.aborted) setError(caught instanceof Error ? caught.message : "权限配置加载失败");
      });
    closeRef.current?.focus();
    const onKeyDown = (event) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      controller.abort();
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [onClose]);

  const changeUser = async (userId, input) => {
    setSavingId(userId);
    setError("");
    try {
      const user = await updateUserAccess(userId, input);
      setConfig((current) => ({
        ...current,
        users: current.users.map((item) => item.id === user.id ? user : item),
      }));
      if (user.id === currentUser.id) onCurrentUserChange();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "用户权限更新失败");
    } finally {
      setSavingId("");
    }
  };

  const togglePermission = (roleId, permission) => {
    setConfig((current) => ({
      ...current,
      roles: current.roles.map((role) => {
        if (role.id !== roleId) return role;
        const selected = role.permissions.includes(permission);
        return {
          ...role,
          permissions: selected
            ? role.permissions.filter((item) => item !== permission)
            : [...role.permissions, permission],
          isDirty: true,
        };
      }),
    }));
  };

  const saveRole = async (role) => {
    setSavingId(role.id);
    setError("");
    try {
      const updated = await updateRolePermissions(role.id, role.permissions);
      setConfig((current) => ({
        ...current,
        roles: current.roles.map((item) => item.id === updated.id ? updated : item),
        users: current.users.map((user) => user.role.id === updated.id
          ? { ...user, role: updated, permissions: updated.permissions }
          : user),
      }));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "角色权限保存失败");
    } finally {
      setSavingId("");
    }
  };

  return (
    <div className="dialog-backdrop" onMouseDown={onClose}>
      <section className="dialog access-dialog" role="dialog" aria-modal="true" aria-labelledby="access-title" onMouseDown={(event) => event.stopPropagation()}>
        <button ref={closeRef} className="dialog-close" onClick={onClose} aria-label="关闭">×</button>
        <header className="access-header">
          <p>Access control</p>
          <h2 id="access-title">权限配置</h2>
          <span>管理成员角色与功能访问范围</span>
        </header>
        <div className="access-tabs" role="tablist">
          <button role="tab" aria-selected={tab === "users"} className={tab === "users" ? "active" : ""} onClick={() => setTab("users")}>成员</button>
          <button role="tab" aria-selected={tab === "roles"} className={tab === "roles" ? "active" : ""} onClick={() => setTab("roles")}>角色权限</button>
        </div>
        {error && <p className="access-error" role="alert">{error}</p>}
        {!config ? (
          <div className="access-loading" aria-busy="true"><span /><span /><span /></div>
        ) : tab === "users" ? (
          <div className="user-access-list">
            {config.users.map((user) => (
              <article className="user-access-row" key={user.id}>
                <div className="user-access-avatar" aria-hidden="true">{user.display_name.slice(0, 1)}</div>
                <div className="user-access-info">
                  <strong>{user.display_name}{user.id === currentUser.id && <em>你</em>}</strong>
                  <span>{user.phone}</span>
                </div>
                <label className="role-select">
                  <span className="visually-hidden">{user.display_name}的角色</span>
                  <select value={user.role.id} disabled={savingId === user.id} onChange={(event) => void changeUser(user.id, { role_id: event.target.value })}>
                    {config.roles.map((role) => <option value={role.id} key={role.id}>{role.name}</option>)}
                  </select>
                </label>
                <label className="status-switch">
                  <input type="checkbox" checked={user.is_active} disabled={savingId === user.id} onChange={(event) => void changeUser(user.id, { is_active: event.target.checked })} />
                  <span aria-hidden="true" />
                  <b>{user.is_active ? "启用" : "停用"}</b>
                </label>
              </article>
            ))}
          </div>
        ) : (
          <div className="role-access-list">
            {config.roles.map((role) => {
              const isAdmin = role.code === "admin";
              return (
                <article className="role-access-card" key={role.id}>
                  <div className="role-access-heading">
                    <div><h3>{role.name}</h3><p>{role.description}</p></div>
                    {!isAdmin && <button disabled={!role.isDirty || savingId === role.id} onClick={() => void saveRole(role)}>{savingId === role.id ? "保存中…" : "保存"}</button>}
                  </div>
                  <div className="permission-grid">
                    {config.permissions.map((permission) => (
                      <label key={permission.code}>
                        <input
                          type="checkbox"
                          checked={isAdmin || role.permissions.includes(permission.code)}
                          disabled={isAdmin}
                          onChange={() => togglePermission(role.id, permission.code)}
                        />
                        <span><strong>{permission.name}</strong><small>{permission.description}</small></span>
                      </label>
                    ))}
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
