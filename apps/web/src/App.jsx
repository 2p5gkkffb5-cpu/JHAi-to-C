import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useNavigationType,
  useParams,
} from "react-router-dom";
import { AccessControlDialog } from "./components/AccessControlDialog.jsx";
import { AgentPage } from "./components/AgentPage.jsx";
import { AuthDialog } from "./components/AuthDialog.jsx";
import { CanvasPage } from "./components/CanvasPage.jsx";
import { ImagePage } from "./components/ImagePage.jsx";
import { ImageAttachmentPicker } from "./components/ImageAttachmentPicker.jsx";
import { VideoClonePage } from "./components/VideoClonePage.jsx";
import { VideoPage } from "./components/VideoPage.jsx";
import { useAuth } from "./hooks/useAuth.js";
import { useContentProject } from "./hooks/useContentProject.js";
import { useImageAttachment } from "./hooks/useImageAttachment.js";

const ASSET = "/brand/";
const BRAND = "/brand/";
const AUTH_ENABLED = import.meta.env.VITE_AUTH_ENABLED === "true";
const scrollPositions = new Map();

const navItems = [
  ["首页", "public-placeholder.svg"],
  ["Agent", "public-placeholder.svg"],
  ["AI视频", "public-placeholder.svg"],
  ["AI图片", "public-placeholder.svg"],
  ["画布", "public-placeholder.svg"],
  ["资产", "public-placeholder.svg"],
];

const tools = [
  ["商详套图", "public-placeholder.svg"],
  ["水印擦除", "public-placeholder.svg"],
  ["字幕擦除", "public-placeholder.svg"],
  ["画质增强", "public-placeholder.svg"],
  ["视频复刻", "public-placeholder.svg"],
];

const gallery = [
  ["public-placeholder.svg", "服饰1:1复刻｜爆款工作流", 18],
  ["public-placeholder.svg", "人物三视图｜告别人脸AI感", 44],
  ["public-placeholder.svg", "真人感教程｜告别AI脸", 18],
  ["public-placeholder.svg", "茂隆掌柜出品｜家居爆款", 112],
  ["public-placeholder.svg", "文生图教程｜提示词模版", 4],
  ["public-placeholder.svg", "自建人脸（模特库）｜秒做人脸资产", 83],
  ["public-placeholder.svg", "TikTok商品详情页｜支持多语言", 10],
  ["public-placeholder.svg", "个护｜白惜复刻 KOC", 1],
  ["public-placeholder.svg", "TikTok视频生成｜适用于任何国家", 24],
  ["public-placeholder.svg", "鞋服｜一键换脸", 0],
  ["public-placeholder.svg", "服装TVC｜原创教程", 3],
  ["public-placeholder.svg", "世界杯带货｜热点跟踪", 3],
  ["public-placeholder.svg", "一键电商套图（完整版）", 19],
  ["public-placeholder.svg", "人物冲出屏幕｜创意玩法", 5],
  ["public-placeholder.svg", "茂隆掌柜出品", 4],
  ["public-placeholder.svg", "纸片人穿搭视频｜创意灵感", 17],
  ["public-placeholder.svg", "数码3C｜外星人创意 KOC", 0],
  ["public-placeholder.svg", "服装｜原创｜痛点场景", 2],
  ["public-placeholder.svg", "服装｜茉寻复刻 KOC", 2],
  ["public-placeholder.svg", "个护｜白惜创意动画", 0],
  ["public-placeholder.svg", "TikTok爆款｜平台精选", 18],
];

function Sidebar({ activeItem, onAction, user, isAuthLoading, authEnabled }) {
  const activeIndex = Math.max(0, navItems.findIndex(([label]) => label === activeItem));

  return (
    <aside className="sidebar" aria-label="主导航">
      <img className="brand" src={`${BRAND}jinghu-mark.png`} alt="鲸互AI" title="鲸互AI" />
      <nav className="side-nav" style={{ "--active-index": activeIndex }}>
        <span className="nav-active-indicator" aria-hidden="true" />
        {navItems.map(([label, icon]) => (
          <button
            type="button"
            className={`nav-button ${label === activeItem ? "active" : ""}`}
            aria-current={label === activeItem ? "page" : undefined}
            key={label}
            onClick={() => onAction(label)}
          >
            <span className="nav-icon" aria-hidden="true">
              <img src={`${ASSET}${icon}`} alt="" />
            </span>
            <span>{label}</span>
          </button>
        ))}
      </nav>
      <div className="side-bottom">
        <button className="credit-button" onClick={() => onAction("订阅")}><img src={`${ASSET}public-placeholder.svg`} alt="" /><small>--</small><b>订阅</b></button>
        {authEnabled && (
          <button
            className={`login-button${user ? " authenticated" : ""}`}
            onClick={() => onAction("登录")}
            aria-label={user ? `账号：${user.display_name}` : "登录或注册"}
            title={user ? user.display_name : "登录或注册"}
          >
            {isAuthLoading ? "…" : user ? user.display_name.slice(0, 1) : "登录"}
          </button>
        )}
        <button className="menu-button" onClick={() => onAction("more")} aria-label="更多"><img src={`${ASSET}public-placeholder.svg`} alt="" /></button>
      </div>
    </aside>
  );
}

function MobileNav({ activeItem, onAction }) {
  const mobile = [navItems[0], navItems[1], navItems[2], navItems[3], navItems[4], ["我的", "public-placeholder.svg"]];
  return (
    <nav className="mobile-nav" aria-label="移动端导航">
      {mobile.map(([label, icon]) => (
        <button className={label === activeItem ? "active" : ""} key={label} onClick={() => onAction(label)}>
          <img src={`${ASSET}${icon}`} alt="" />
          <span>{label}</span>
        </button>
      ))}
    </nav>
  );
}

function Composer({ error, isSubmitting, onSubmit }) {
  const modes = [
    { label: "Agent 模式", value: "full_creation" },
    { label: "智能模式", value: "auto" },
    { label: "视频生成", value: "video_generation" },
    { label: "图片生成", value: "image_generation" },
    { label: "一站式包装", value: "brand_packaging" },
  ];
  const [mode, setMode] = useState(modes[0]);
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");
  const imageAttachment = useImageAttachment();
  const modeWrapRef = useRef(null);
  const modeButtonRef = useRef(null);
  const canSubmit = Boolean(value.trim())
    && !isSubmitting
    && !imageAttachment.isUploading
    && !imageAttachment.error
    && (mode.value !== "brand_packaging" || imageAttachment.references.length > 0);

  useEffect(() => {
    if (!open) return undefined;

    const closeOnOutsideClick = (event) => {
      if (!modeWrapRef.current?.contains(event.target)) setOpen(false);
    };
    const closeOnEscape = (event) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      modeButtonRef.current?.focus();
    };

    document.addEventListener("pointerdown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  const submit = async () => {
    const cleanValue = value.trim();
    if (!cleanValue || !canSubmit) return;
    try {
      await onSubmit(
        cleanValue,
        mode.value,
        imageAttachment.references,
      );
      setValue("");
      imageAttachment.clear();
    } catch {
      // The request stays in the composer so the user can retry.
    }
  };

  return (
    <section className="composer" aria-label="AI 创作输入框">
      <ImageAttachmentPicker
        attachments={imageAttachment.attachments}
        error={imageAttachment.error}
        onRemove={imageAttachment.remove}
        onRetry={imageAttachment.retry}
        onSelect={imageAttachment.select}
      />
      <textarea
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder={mode.value === "brand_packaging" ? "填写品牌/店铺名称、主营内容、目标人群和偏好风格…" : "结合参考、输入文字或 @ 主体，说说今天想做什么。"}
        aria-label={mode.value === "brand_packaging" ? "填写品牌或店铺基本信息" : "描述你的创作需求"}
      />
      <div className="mode-wrap" ref={modeWrapRef}>
        <button ref={modeButtonRef} className={`mode-button${mode.value === "full_creation" ? " is-agent" : ""}`} onClick={() => setOpen(!open)} aria-haspopup="listbox" aria-expanded={open} aria-controls={open ? "creation-mode-menu" : undefined}>
          <img src={`${ASSET}public-placeholder.svg`} alt="" />
          {mode.label}
          <img className="chevron" src={`${ASSET}public-placeholder.svg`} alt="" />
        </button>
        {open && (
          <div className="mode-menu" id="creation-mode-menu" role="listbox" aria-label="生成模式">
            {modes.map((item) => (
              <button role="option" aria-selected={item.value === mode.value} className={item.value === mode.value ? "selected" : ""} key={item.value} onClick={() => { setMode(item); setOpen(false); }}>
                {item.label}
              </button>
            ))}
          </div>
        )}
      </div>
      <button className={`send-button${isSubmitting ? " is-loading" : ""}`} disabled={!canSubmit} aria-label={isSubmitting ? "正在创建任务" : "发送"} onClick={() => void submit()}>
        <img src={`${ASSET}public-placeholder.svg`} alt="" />
      </button>
      {mode.value === "brand_packaging" && imageAttachment.references.length === 0 && !imageAttachment.isUploading && (
        <p className="composer-guidance">请先上传产品、店铺或品牌参考图片</p>
      )}
      {(error || imageAttachment.error) && (
        <p className="composer-error" role="alert">
          {error?.message || imageAttachment.error}
        </p>
      )}
    </section>
  );
}

function QuickEntries({ onAction }) {
  return (
    <section className="quick-entries" aria-label="快捷创作">
      {tools.map(([title, image]) => (
        <button className="tool-card" key={title} onClick={() => onAction(title)}>
          <img src={`${ASSET}${image}`} alt="" />
          <strong>{title}</strong>
          <img className="tool-arrow" src={`${ASSET}public-placeholder.svg`} alt="" />
        </button>
      ))}
    </section>
  );
}

function GalleryCard({ data, itemIndex, onToast }) {
  const [, title, initialLikes] = data;
  const [liked, setLiked] = useState(false);
  return (
    <article className="gallery-card" onClick={() => onToast(title)}>
      <div className={`gallery-placeholder placeholder-${itemIndex % 5}`} role="img" aria-label={`${title}占位图`} />
      <div className="card-overlay">
        <span className="card-title"><img src={`${ASSET}public-placeholder.svg`} alt="" />{title}</span>
        <button className={liked ? "liked" : ""} aria-label={liked ? "取消喜欢" : "喜欢"} onClick={(event) => { event.stopPropagation(); setLiked(!liked); }}>
          <img src={`${ASSET}public-placeholder.svg`} alt="" />{initialLikes + (liked ? 1 : 0)}
        </button>
      </div>
    </article>
  );
}

function Gallery({ onToast }) {
  const desktopColumns = useMemo(() => [
    [0, 7, 11, 17], [1, 5, 15], [3, 6, 12, 16], [2, 8, 14, 18], [4, 9, 13, 19, 20],
  ], []);
  const mobileColumns = useMemo(() => [
    [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20], [1, 3, 5, 7, 9, 11, 13, 15, 17, 19],
  ], []);
  return (
    <>
      <div className="gallery desktop-gallery">
        {desktopColumns.map((column, index) => <div className="gallery-column" key={index}>{column.map((item) => <GalleryCard key={item} data={gallery[item]} itemIndex={item} onToast={onToast} />)}</div>)}
      </div>
      <div className="gallery mobile-gallery">
        {mobileColumns.map((column, index) => <div className="gallery-column" key={index}>{column.map((item) => <GalleryCard key={item} data={gallery[item]} itemIndex={item} onToast={onToast} />)}</div>)}
      </div>
    </>
  );
}

export function App() {
  const [tab, setTab] = useState("发现");
  const [toast, setToast] = useState("");
  const [panel, setPanel] = useState(null);
  const [imagePrompt, setImagePrompt] = useState("");
  const [imageReferences, setImageReferences] = useState([]);
  const [videoPrompt, setVideoPrompt] = useState("");
  const [videoReferences, setVideoReferences] = useState([]);
  const auth = useAuth();
  const hasWorkspaceAccess = !AUTH_ENABLED || Boolean(auth.user);
  const accountId = AUTH_ENABLED ? auth.user?.id || "guest" : "guest";
  const workflow = useContentProject({
    enabled: hasWorkspaceAccess,
    accountId,
  });
  const location = useLocation();
  const navigate = useNavigate();
  const page = getPageFromPath(location.pathname);
  const closePanel = useCallback(() => setPanel(null), []);
  const consumeVideoSeed = useCallback(() => {
    setVideoPrompt("");
    setVideoReferences([]);
  }, []);

  useEffect(() => {
    if (!AUTH_ENABLED || auth.isLoading || auth.user || page === "home") return;
    navigate("/", { replace: true });
    setPanel("auth");
  }, [auth.isLoading, auth.user, navigate, page]);

  const showToast = (message) => { setToast(message); window.clearTimeout(window.__toastTimer); window.__toastTimer = window.setTimeout(() => setToast(""), 2200); };
  const onAction = (action) => {
    if (action === "首页") {
      if (location.pathname === "/") window.scrollTo({ top: 0, left: 0, behavior: "auto" });
      else navigate("/");
    }
    else if (action === "Agent" && hasWorkspaceAccess) navigate(workflow.projectId ? `/agent/${encodeURIComponent(workflow.projectId)}` : "/agent");
    else if (action === "AI视频" && hasWorkspaceAccess) navigate("/video");
    else if (action === "AI图片" && hasWorkspaceAccess) navigate("/image");
    else if (action === "画布" && hasWorkspaceAccess) navigate("/canvas");
    else if (action === "视频复刻" && hasWorkspaceAccess) navigate("/video-clone");
    else if (AUTH_ENABLED && ["Agent", "AI视频", "AI图片", "画布", "视频复刻", "登录", "我的"].includes(action)) setPanel("auth");
    else if (action === "我的") showToast("测试模式未启用账号系统");
    else if (action === "more") setPanel("more");
    else showToast(`${action}：本地静态预览`);
  };
  const createProject = async (requestText, requestedMode, references = []) => {
    if (AUTH_ENABLED && !auth.user) {
      setPanel("auth");
      showToast("请先登录后再开始创作");
      throw new Error("请先登录后再开始创作");
    }
    if (requestedMode === "image_generation") {
      setImagePrompt(requestText);
      setImageReferences(references);
      navigate("/image");
      return;
    }
    if (requestedMode === "video_generation") {
      setVideoPrompt(requestText);
      setVideoReferences(references);
      navigate("/video");
      return;
    }
    const project = await workflow.createAndStart(requestText, requestedMode, references);
    navigate(`/agent/${encodeURIComponent(project.id)}`);
    showToast(requestedMode === "auto" ? "正在智能判断创作方式" : "创作任务已创建");
  };
  const startNewConversation = async () => {
    if (workflow.project && !["completed", "failed", "cancelled"].includes(workflow.project.status)) {
      try {
        await workflow.cancel();
      } catch {
        return;
      }
    }
    workflow.reset();
    navigate("/agent");
  };
  const selectProject = (projectId) => {
    workflow.selectProject(projectId);
    navigate(`/agent/${encodeURIComponent(projectId)}`);
  };

  return (
    <div className="app-shell">
      <ScrollManager />
      {page !== "canvas" && (
        <Sidebar
          activeItem={page === "agent" ? "Agent" : page === "video" ? "AI视频" : page === "image" ? "AI图片" : "首页"}
          onAction={onAction}
          user={auth.user}
          isAuthLoading={auth.isLoading}
          authEnabled={AUTH_ENABLED}
        />
      )}
      <Routes>
        <Route
          path="/"
          element={(
            <main className="page">
              <div className="page-inner">
                <header className="hero">
                  <p className="hero-kicker">今天想创作什么？</p>
                  <h1><img src={`${BRAND}jinghu-mark.png`} alt="" />鲸互AI创作空间</h1>
                  <Composer
                    error={!workflow.projectId ? workflow.error : null}
                    isSubmitting={workflow.isCreating}
                    onSubmit={createProject}
                  />
                </header>
                <QuickEntries onAction={onAction} />
                <section className="discover" aria-label="作品发现">
                  <div className="tabs" role="tablist">
                    {["发现", "视频", "图片", "画布"].map((item) => <button role="tab" aria-selected={tab === item} className={tab === item ? "active" : ""} onClick={() => setTab(item)} key={item}>{item}</button>)}
                  </div>
                  <Gallery onToast={showToast} />
                </section>
                <footer>Copyright © 蓝色矩阵 <span>|</span> 网站备案号：浙ICP备2024085888号-4 <span>|</span> <button onClick={() => showToast("联系我们：本地静态预览")}>联系我们</button></footer>
              </div>
            </main>
          )}
        />
        <Route
          path="/agent"
          element={<AgentRoute onAction={onAction} onCreateProject={createProject} onNewConversation={startNewConversation} onSelectProject={selectProject} workflow={workflow} />}
        />
        <Route
          path="/agent/:projectId"
          element={<AgentRoute onAction={onAction} onCreateProject={createProject} onNewConversation={startNewConversation} onSelectProject={selectProject} workflow={workflow} />}
        />
        <Route
          path="/video"
          element={(
            <VideoPage
              key={accountId}
              enabled={hasWorkspaceAccess}
              ownerId={accountId}
              initialPrompt={videoPrompt}
              initialReferences={videoReferences}
              onInitialInputConsumed={consumeVideoSeed}
            />
          )}
        />
        <Route
          path="/video-clone"
          element={hasWorkspaceAccess ? (
            <VideoClonePage
              key={accountId}
              enabled
              onBack={() => navigate("/")}
            />
          ) : <Navigate replace to="/" />}
        />
        <Route
          path="/image"
          element={<ImagePage initialPrompt={imagePrompt} initialReferences={imageReferences} />}
        />
        <Route
          path="/canvas"
          element={hasWorkspaceAccess ? (
            <CanvasPage
              key={accountId}
              ownerId={accountId}
              onOpenAgent={() => onAction("Agent")}
              onOpenHome={() => onAction("首页")}
            />
          ) : <Navigate replace to="/" />}
        />
        <Route path="*" element={<Navigate replace to="/" />} />
      </Routes>
      {page !== "canvas" && (
        <MobileNav activeItem={page === "agent" ? "Agent" : page === "video" ? "AI视频" : page === "image" ? "AI图片" : "首页"} onAction={onAction} />
      )}
      {toast && <div className="toast" role="status">{toast}</div>}
      {AUTH_ENABLED && panel === "auth" && (
        <AuthDialog
          user={auth.user}
          onClose={closePanel}
          onLogin={auth.signIn}
          onRegister={auth.signUp}
          onLogout={auth.signOut}
          onOpenAccess={() => setPanel("access")}
        />
      )}
      {AUTH_ENABLED && panel === "access" && auth.user && (
        <AccessControlDialog
          currentUser={auth.user}
          onClose={closePanel}
          onCurrentUserChange={auth.refresh}
        />
      )}
      {panel === "more" && (
        <div className="dialog-backdrop" onMouseDown={() => setPanel(null)}>
          <section className="dialog" role="dialog" aria-modal="true" aria-label="更多" onMouseDown={(event) => event.stopPropagation()}>
            <button className="dialog-close" onClick={() => setPanel(null)} aria-label="关闭">×</button>
            <h2>服务与协议</h2>
            <button onClick={() => showToast("用户协议：本地静态预览")}>用户协议</button>
            <button onClick={() => showToast("隐私政策：本地静态预览")}>隐私政策</button>
            <button onClick={() => showToast("联系我们：本地静态预览")}>联系我们</button>
          </section>
        </div>
      )}
    </div>
  );
}

function AgentRoute({ onAction, onCreateProject, onNewConversation, onSelectProject, workflow }) {
  const { projectId } = useParams();

  useEffect(() => {
    if (projectId && projectId !== workflow.projectId) workflow.selectProject(projectId);
  }, [projectId, workflow.projectId, workflow.selectProject]);

  return (
    <AgentPage
      onAction={onAction}
      onCreateProject={onCreateProject}
      onNewConversation={onNewConversation}
      onSelectProject={onSelectProject}
      workflow={workflow}
    />
  );
}

function ScrollManager() {
  const location = useLocation();
  const navigationType = useNavigationType();

  useLayoutEffect(() => {
    const savedPosition = navigationType === "POP" ? scrollPositions.get(location.key) : null;
    window.scrollTo({
      top: savedPosition?.top || 0,
      left: savedPosition?.left || 0,
      behavior: "auto",
    });

    return () => {
      scrollPositions.set(location.key, { top: window.scrollY, left: window.scrollX });
    };
  }, [location.key, navigationType]);

  return null;
}

function getPageFromPath(pathname) {
  if (pathname === "/video-clone") return "video-clone";
  if (pathname === "/video") return "video";
  if (pathname === "/image") return "image";
  if (pathname === "/canvas") return "canvas";
  if (pathname === "/agent" || pathname.startsWith("/agent/")) return "agent";
  return "home";
}
