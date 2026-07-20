import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const ASSET = "/brand/";
const BRAND = "/brand/";
const STORAGE_PREFIX = "jinghu-canvas-workspace-v2";
const NODE_WIDTH = 252;

const nodeCatalog = {
  script: { label: "脚本", icon: "public-placeholder.svg", height: 190 },
  image: { label: "画面", icon: "public-placeholder.svg", height: 236 },
  video: { label: "视频", icon: "public-placeholder.svg", height: 236 },
  output: { label: "成片", icon: "public-placeholder.svg", height: 190 },
};

const initialNodes = [];
const initialEdges = [];

const quickStarts = [
  { id: "story", label: "故事脚本生成", type: "script", image: "public-placeholder.svg", icon: "public-placeholder.svg" },
  { id: "character", label: "角色三视图", type: "image", image: "public-placeholder.svg", icon: "public-placeholder.svg" },
  { id: "first-frame", label: "首帧图生视频", type: "video", image: "public-placeholder.svg", icon: "public-placeholder.svg" },
  { id: "audio", label: "音频生视频", type: "video", image: "public-placeholder.svg", icon: "public-placeholder.svg" },
];

export function getCanvasStorageKey(ownerId) {
  return `${STORAGE_PREFIX}:${encodeURIComponent(ownerId || "guest")}`;
}

function loadWorkspace(ownerId) {
  try {
    const saved = JSON.parse(window.localStorage.getItem(getCanvasStorageKey(ownerId)));
    if (Array.isArray(saved?.nodes) && Array.isArray(saved?.edges)) return saved;
  } catch {
    // A malformed draft falls back to the curated starter canvas.
  }
  return { title: "未命名工作区", nodes: initialNodes, edges: initialEdges };
}

function getNodeHeight(node) {
  return nodeCatalog[node.type]?.height || 190;
}

function CanvasNode({ node, isConnecting, isSelected, onConnect, onSelect, onStartDrag, onUpdate }) {
  const meta = nodeCatalog[node.type];

  return (
    <article
      className={`canvas-node canvas-node--${node.type}${isSelected ? " is-selected" : ""}`}
      style={{ left: node.x, top: node.y, width: NODE_WIDTH, height: getNodeHeight(node) }}
      onPointerDown={(event) => {
        if (event.target.closest("button, textarea, input")) return;
        onSelect(node.id);
      }}
    >
      <button
        type="button"
        className={`canvas-port canvas-port--input${isConnecting ? " is-ready" : ""}`}
        aria-label={`连接到${node.title}`}
        onClick={() => onConnect("input", node.id)}
      />
      <header className="canvas-node__header" onPointerDown={(event) => onStartDrag(event, node)}>
        <span className="canvas-node__icon"><img src={`${ASSET}${meta.icon}`} alt="" /></span>
        <div>
          <small>{meta.label}</small>
          <input
            value={node.title}
            aria-label={`${meta.label}节点标题`}
            onChange={(event) => onUpdate(node.id, { title: event.target.value })}
          />
        </div>
        <span className="canvas-node__drag" aria-hidden="true">拖动</span>
      </header>

      {node.type === "script" && (
        <textarea
          className="canvas-node__script"
          value={node.content}
          aria-label="脚本内容"
          onChange={(event) => onUpdate(node.id, { content: event.target.value })}
        />
      )}

      {(node.type === "image" || node.type === "video") && (
        <div className="canvas-node__media">
          <img src={node.image} alt="" draggable="false" />
          {node.type === "video" && <span>00:06</span>}
        </div>
      )}

      {node.type === "output" && (
        <div className="canvas-node__output">
          <img src={`${ASSET}public-placeholder.svg`} alt="" />
          <strong>项目成片</strong>
          <span>H.264 · 竖版视频</span>
        </div>
      )}

      {node.type !== "script" && (
        <p className="canvas-node__description">{node.content}</p>
      )}

      <footer>
        <span className={`canvas-node__status status-${node.status}`}>{node.status}</span>
        <button type="button" onClick={() => onSelect(node.id)}>编辑参数</button>
      </footer>
      <button
        type="button"
        className="canvas-port canvas-port--output"
        aria-label={`从${node.title}开始连线`}
        onClick={() => onConnect("output", node.id)}
      />
    </article>
  );
}

function CanvasInspector({ node, onDelete, onUpdate }) {
  if (!node) return null;

  const meta = nodeCatalog[node.type];
  return (
    <aside className="canvas-inspector" aria-label="节点设置">
      <header>
        <div>
          <span>{meta.label}节点</span>
          <h2>{node.title || "未命名节点"}</h2>
        </div>
        <button type="button" onClick={() => onDelete(node.id)}>删除</button>
      </header>
      <label>
        节点名称
        <input value={node.title} onChange={(event) => onUpdate(node.id, { title: event.target.value })} />
      </label>
      <label>
        创作描述
        <textarea value={node.content} onChange={(event) => onUpdate(node.id, { content: event.target.value })} />
      </label>
      {(node.type === "image" || node.type === "video") && (
        <>
          <label>
            画面比例
            <select defaultValue="9:16"><option>9:16</option><option>16:9</option><option>1:1</option></select>
          </label>
          <label>
            生成模型
            <select defaultValue={node.type === "video" ? "Seedance 2.0" : "鲸互图像 2"}>
              <option>{node.type === "video" ? "Seedance 2.0" : "鲸互图像 2"}</option>
              <option>{node.type === "video" ? "可灵 2.1" : "通用写实"}</option>
            </select>
          </label>
        </>
      )}
      <section>
        <span>输入关系</span>
        <p>当前节点会同时读取所有连入节点的内容与素材。</p>
      </section>
    </aside>
  );
}

export function CanvasPage({ onOpenAgent, onOpenHome, ownerId }) {
  const saved = useMemo(() => loadWorkspace(ownerId), [ownerId]);
  const [title, setTitle] = useState(saved.title || "未命名画布");
  const [nodes, setNodes] = useState(saved.nodes);
  const [edges, setEdges] = useState(saved.edges);
  const [selectedId, setSelectedId] = useState(null);
  const [mode, setMode] = useState("select");
  const [viewMode, setViewMode] = useState("workflow");
  const [viewport, setViewport] = useState({ x: 0, y: 0, zoom: 1 });
  const [addMenuOpen, setAddMenuOpen] = useState(false);
  const [connectionSource, setConnectionSource] = useState(null);
  const [saveLabel, setSaveLabel] = useState("已自动保存");
  const stageRef = useRef(null);
  const gestureRef = useRef(null);

  const selectedNode = nodes.find((node) => node.id === selectedId) || null;

  useEffect(() => {
    setSaveLabel("保存中…");
    const timer = window.setTimeout(() => {
      window.localStorage.setItem(
        getCanvasStorageKey(ownerId),
        JSON.stringify({ title, nodes, edges }),
      );
      setSaveLabel("已自动保存");
    }, 260);
    return () => window.clearTimeout(timer);
  }, [edges, nodes, ownerId, title]);

  const updateNode = useCallback((nodeId, patch) => {
    setNodes((current) => current.map((node) => (node.id === nodeId ? { ...node, ...patch } : node)));
  }, []);

  const addNode = (type, position, overrides = {}) => {
    const rect = stageRef.current?.getBoundingClientRect();
    const centerX = position?.x ?? ((rect?.width || 900) / 2 - viewport.x) / viewport.zoom - NODE_WIDTH / 2;
    const centerY = position?.y ?? ((rect?.height || 650) / 2 - viewport.y) / viewport.zoom - getNodeHeight({ type }) / 2;
    const id = `${type}-${Date.now()}`;
    const next = {
      id,
      type,
      title: type === "script" ? "新脚本" : type === "image" ? "新分镜画面" : type === "video" ? "新视频片段" : "新成片",
      content: type === "script" ? "写下这一步需要完成的叙事内容。" : "描述镜头、动作、光线与风格。",
      image: type === "image" ? `${ASSET}public-placeholder.svg` : `${ASSET}public-placeholder.svg`,
      x: Math.round(centerX),
      y: Math.round(centerY),
      status: type === "output" ? "待合成" : type === "video" ? "待生成" : "草稿",
      ...overrides,
    };
    setNodes((current) => [...current, next]);
    setSelectedId(id);
    setAddMenuOpen(false);
  };

  const startFromTemplate = (template) => {
    const templateCopy = {
      story: { title: "故事脚本生成", content: "围绕产品卖点、使用场景和目标人群生成完整短片脚本。" },
      character: { title: "角色三视图", content: "保持角色外观、服装与比例一致。", image: `${ASSET}${template.image}` },
      "first-frame": { title: "首帧图生视频", content: "从首帧延展镜头运动与人物动作。", image: `${ASSET}${template.image}` },
      audio: { title: "音频生视频", content: "根据音频节奏规划镜头与画面变化。", image: `${ASSET}${template.image}` },
    }[template.id];
    addNode(template.type, undefined, templateCopy);
  };

  const deleteNode = useCallback((nodeId) => {
    setNodes((current) => current.filter((node) => node.id !== nodeId));
    setEdges((current) => current.filter((edge) => edge.from !== nodeId && edge.to !== nodeId));
    setSelectedId((current) => (current === nodeId ? null : current));
    setConnectionSource((current) => (current === nodeId ? null : current));
  }, []);

  const connectNode = (port, nodeId) => {
    if (port === "output") {
      setConnectionSource((current) => (current === nodeId ? null : nodeId));
      return;
    }
    if (!connectionSource || connectionSource === nodeId) return;
    setEdges((current) => {
      if (current.some((edge) => edge.from === connectionSource && edge.to === nodeId)) return current;
      return [...current, { id: `${connectionSource}-${nodeId}-${Date.now()}`, from: connectionSource, to: nodeId }];
    });
    setConnectionSource(null);
  };

  const startNodeDrag = (event, node) => {
    if (mode !== "select") return;
    event.preventDefault();
    event.stopPropagation();
    setSelectedId(node.id);
    gestureRef.current = {
      kind: "node",
      pointerId: event.pointerId,
      nodeId: node.id,
      startX: event.clientX,
      startY: event.clientY,
      nodeX: node.x,
      nodeY: node.y,
    };
    stageRef.current?.setPointerCapture?.(event.pointerId);
  };

  const startStageGesture = (event) => {
    if (event.target.closest(".canvas-node, .canvas-chrome")) return;
    if (mode === "select") setSelectedId(null);
    if (mode !== "pan" && event.button !== 1) return;
    gestureRef.current = {
      kind: "pan",
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      viewX: viewport.x,
      viewY: viewport.y,
    };
    stageRef.current?.setPointerCapture?.(event.pointerId);
  };

  const createNodeAtPointer = (event) => {
    if (event.target.closest(".canvas-node, .canvas-chrome")) return;
    const rect = stageRef.current?.getBoundingClientRect();
    if (!rect) return;
    addNode("script", {
      x: (event.clientX - rect.left - viewport.x) / viewport.zoom - NODE_WIDTH / 2,
      y: (event.clientY - rect.top - viewport.y) / viewport.zoom - getNodeHeight({ type: "script" }) / 2,
    });
  };

  const moveGesture = (event) => {
    const gesture = gestureRef.current;
    if (!gesture || gesture.pointerId !== event.pointerId) return;
    if (gesture.kind === "pan") {
      setViewport((current) => ({
        ...current,
        x: gesture.viewX + event.clientX - gesture.startX,
        y: gesture.viewY + event.clientY - gesture.startY,
      }));
      return;
    }
    const nextX = gesture.nodeX + (event.clientX - gesture.startX) / viewport.zoom;
    const nextY = gesture.nodeY + (event.clientY - gesture.startY) / viewport.zoom;
    updateNode(gesture.nodeId, { x: Math.round(nextX), y: Math.round(nextY) });
  };

  const endGesture = (event) => {
    if (gestureRef.current?.pointerId === event.pointerId) gestureRef.current = null;
    if (stageRef.current?.hasPointerCapture?.(event.pointerId)) stageRef.current.releasePointerCapture(event.pointerId);
  };

  const setZoom = useCallback((zoom, anchor) => {
    setViewport((current) => {
      const nextZoom = Math.min(1.35, Math.max(0.42, zoom));
      if (!anchor) return { ...current, zoom: nextZoom };
      const worldX = (anchor.x - current.x) / current.zoom;
      const worldY = (anchor.y - current.y) / current.zoom;
      return { x: anchor.x - worldX * nextZoom, y: anchor.y - worldY * nextZoom, zoom: nextZoom };
    });
  }, []);

  const onWheel = (event) => {
    event.preventDefault();
    const rect = stageRef.current.getBoundingClientRect();
    setZoom(viewport.zoom * (event.deltaY > 0 ? 0.92 : 1.08), { x: event.clientX - rect.left, y: event.clientY - rect.top });
  };

  const fitCanvas = () => setViewport(nodes.length ? { x: 70, y: 70, zoom: 0.64 } : { x: 0, y: 0, zoom: 1 });

  const previewWorkflow = () => {
    const connectedTargets = new Set(edges.map((edge) => edge.to));
    setNodes((current) => current.map((node) => (
      node.type === "video" || node.type === "output"
        ? { ...node, status: connectedTargets.has(node.id) ? "路径已连接" : "缺少输入" }
        : node
    )));
    setSaveLabel("路径预览只检查画布连线，不会执行生成");
  };

  const edgePaths = edges.map((edge) => {
    const from = nodes.find((node) => node.id === edge.from);
    const to = nodes.find((node) => node.id === edge.to);
    if (!from || !to) return null;
    const x1 = from.x + NODE_WIDTH;
    const y1 = from.y + getNodeHeight(from) / 2;
    const x2 = to.x;
    const y2 = to.y + getNodeHeight(to) / 2;
    const curve = Math.max(90, Math.abs(x2 - x1) * 0.42);
    return <path key={edge.id} d={`M ${x1} ${y1} C ${x1 + curve} ${y1}, ${x2 - curve} ${y2}, ${x2} ${y2}`} />;
  });

  return (
    <main className="canvas-page">
      <section className="canvas-workspace">
        <div
          ref={stageRef}
          className={`canvas-surface mode-${mode}${gestureRef.current?.kind === "pan" ? " is-panning" : ""}`}
          data-testid="canvas-surface"
          onPointerDown={startStageGesture}
          onPointerMove={moveGesture}
          onPointerUp={endGesture}
          onPointerCancel={endGesture}
          onDoubleClick={createNodeAtPointer}
          onWheel={onWheel}
        >
          <div className="canvas-top-left canvas-chrome">
            <button type="button" className="canvas-home-button" aria-label="返回首页" onClick={onOpenHome}>
              <img src={`${BRAND}jinghu-mark.png`} alt="鲸互AI" />
            </button>
            <span />
            <input value={title} aria-label="工作区名称" onChange={(event) => setTitle(event.target.value)} />
            <span />
            <button type="button" className="canvas-name-button">画布 1 <img src={`${ASSET}public-placeholder.svg`} alt="" /></button>
          </div>

          <div className="canvas-view-switch canvas-chrome" role="tablist" aria-label="画布视图">
            <button type="button" role="tab" aria-selected={viewMode === "workflow"} className={viewMode === "workflow" ? "active" : ""} onClick={() => setViewMode("workflow")}>
              <img src={`${ASSET}public-placeholder.svg`} alt="" />工作流
            </button>
            <button type="button" role="tab" aria-selected={viewMode === "storyboard"} className={viewMode === "storyboard" ? "active" : ""} onClick={() => setViewMode("storyboard")}>
              <img src={`${ASSET}public-placeholder.svg`} alt="" />故事板
            </button>
          </div>

          <div className="canvas-prototype-note canvas-chrome" role="note">
            本地原型 · 路径预览不会执行生成
          </div>

          <div className="canvas-top-actions canvas-chrome">
            <button type="button" aria-label="分享画布" title="分享画布" onClick={() => setSaveLabel("分享设置已打开")}><img src={`${ASSET}public-placeholder.svg`} alt="" /></button>
            <button type="button" aria-label="资产空间" title="资产空间"><img src={`${ASSET}public-placeholder.svg`} alt="" /></button>
            <div className="canvas-credit"><img src={`${ASSET}public-placeholder.svg`} alt="" /><span>100</span><img src={`${ASSET}public-placeholder.svg`} alt="" /></div>
            <button type="button" className="canvas-agent-button" onClick={onOpenAgent}><img src={`${ASSET}public-placeholder.svg`} alt="" />Agent</button>
          </div>

          {nodes.length === 0 && (
            <section className="canvas-starter canvas-chrome" aria-label="快捷开始">
              <p><img src={`${ASSET}public-placeholder.svg`} alt="" /><strong>双击画布</strong><span>自由生成节点</span></p>
              <div>
                {quickStarts.map((template) => (
                  <button type="button" key={template.id} onClick={() => startFromTemplate(template)}>
                    <img className="canvas-starter__cover" src={`${ASSET}${template.image}`} alt="" />
                    <span className="canvas-starter__label"><img src={`${ASSET}${template.icon}`} alt="" />{template.label}</span>
                  </button>
                ))}
              </div>
            </section>
          )}

          {connectionSource && (
            <div className="canvas-connection-tip" role="status">选择另一个节点左侧的连接点</div>
          )}

          <div className="canvas-viewport" style={{ transform: `translate(${viewport.x}px, ${viewport.y}px) scale(${viewport.zoom})` }}>
            <svg className="canvas-edges" width="1800" height="1000" aria-hidden="true">
              {edgePaths}
            </svg>
            {nodes.map((node) => (
              <CanvasNode
                key={node.id}
                node={node}
                isConnecting={Boolean(connectionSource) && connectionSource !== node.id}
                isSelected={selectedId === node.id}
                onConnect={connectNode}
                onSelect={setSelectedId}
                onStartDrag={startNodeDrag}
                onUpdate={updateNode}
              />
            ))}
          </div>

          <div className="canvas-bottom-left canvas-chrome">
            <button type="button"><img src={`${ASSET}public-placeholder.svg`} alt="" />资产管理</button>
            <button type="button" aria-label="节点总览" title="节点总览"><img src={`${ASSET}public-placeholder.svg`} alt="" /></button>
            <button type="button" aria-label="定位节点" title="定位节点" onClick={fitCanvas}><img src={`${ASSET}public-placeholder.svg`} alt="" /></button>
            <button type="button" aria-label="切换漫游" title="切换漫游" onClick={() => setMode((current) => current === "pan" ? "select" : "pan")}><img src={`${ASSET}public-placeholder.svg`} alt="" /></button>
            <button type="button" aria-label="吸附连线" title="吸附连线"><img src={`${ASSET}public-placeholder.svg`} alt="" /></button>
            <span>{Math.round(viewport.zoom * 100)}%</span>
          </div>

          <div className="canvas-bottom-dock canvas-chrome" aria-label="画布工具栏">
            <div className="canvas-add-wrap">
              <button type="button" className={`canvas-dock-primary${addMenuOpen ? " active" : ""}`} aria-label="添加节点" aria-expanded={addMenuOpen} onClick={() => setAddMenuOpen((open) => !open)}>
                <img src={`${ASSET}public-placeholder.svg`} alt="" />
              </button>
              {addMenuOpen && (
                <div className="canvas-add-menu">
                  {Object.entries(nodeCatalog).map(([type, meta]) => (
                    <button type="button" key={type} onClick={() => addNode(type)}>
                      <img src={`${ASSET}${meta.icon}`} alt="" />
                      <span><strong>{meta.label}</strong><small>{type === "script" ? "创意、脚本或旁白" : type === "image" ? "角色、场景或分镜" : type === "video" ? "动态镜头片段" : "合并并导出成片"}</small></span>
                    </button>
                  ))}
                </div>
              )}
            </div>
            <button type="button" aria-label="连线模式" title="连线模式" onClick={() => setMode("select")}><img src={`${ASSET}public-placeholder.svg`} alt="" /></button>
            <button type="button" aria-label="添加画面" title="添加画面" onClick={() => addNode("image")}><img src={`${ASSET}public-placeholder.svg`} alt="" /></button>
            <button type="button" aria-label="添加角色" title="添加角色" onClick={() => startFromTemplate(quickStarts[1])}><img src={`${ASSET}public-placeholder.svg`} alt="" /></button>
            <button type="button" aria-label="预览路径" title="仅预览画布连线" disabled={nodes.length === 0} onClick={previewWorkflow}><img src={`${ASSET}public-placeholder.svg`} alt="" /></button>
            <span />
            <button type="button" aria-label="快捷键" title="快捷键"><img src={`${ASSET}public-placeholder.svg`} alt="" /></button>
            <button type="button" aria-label="帮助" title="帮助" onClick={() => setSaveLabel("双击画布或使用加号创建节点")}><img src={`${ASSET}public-placeholder.svg`} alt="" /></button>
          </div>

          <div className="canvas-save-state canvas-chrome"><i />{saveLabel}</div>
        </div>
        <CanvasInspector node={selectedNode} onDelete={deleteNode} onUpdate={updateNode} />
      </section>
    </main>
  );
}
