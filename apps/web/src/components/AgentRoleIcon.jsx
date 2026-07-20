const ICONS = {
  intent_router: <><circle cx="12" cy="6" r="2" /><circle cx="6" cy="18" r="2" /><circle cx="18" cy="18" r="2" /><path d="M12 8v3m0 0-6 5m6-5 6 5" /></>,
  director: <><path d="M4 8h16v11H4zM4 8l3-4h4L8 8m5 0 3-4h4l-3 4" /><path d="M8 13h8" /></>,
  research: <><circle cx="10.5" cy="10.5" r="5.5" /><path d="m15 15 4.5 4.5M8 8.5h5M8 11.5h3" /></>,
  production: <><path d="m12 3 8 4-8 4-8-4 8-4Z" /><path d="m4 12 8 4 8-4M4 17l8 4 8-4" /></>,
  brand_packaging: <><path d="m4 7 8-4 8 4-8 4-8-4Z" /><path d="M4 7v10l8 4 8-4V7M12 11v10" /><path d="M8 5l8 4" /></>,
  strategy: <><circle cx="12" cy="12" r="8.5" /><path d="m15.5 8.5-2 5-5 2 2-5 5-2Z" /></>,
  production_coordinator: <><path d="M10 6h10M10 12h10M10 18h10" /><path d="m4 6 1.5 1.5L8 4.5m-4 7.5 1.5 1.5L8 10.5m-4 7.5 1.5 1.5L8 16.5" /></>,
  copywriting: <><path d="m4 20 4.5-1 10-10a2.1 2.1 0 0 0-3-3l-10 10L4 20Z" /><path d="m14 7 3 3M8.5 19l-3-3" /></>,
  storyboard: <><rect x="3.5" y="4" width="17" height="16" rx="1.5" /><path d="M3.5 10h17M9 4v16M9 15h11" /></>,
  video_prompt: <><rect x="3" y="4" width="18" height="16" rx="2" /><path d="m7 9 3 3-3 3m6 0h4" /></>,
  reviewer: <><path d="M12 3 19 6v5c0 4.5-2.8 8-7 10-4.2-2-7-5.5-7-10V6l7-3Z" /><path d="m8.5 12 2.2 2.2 4.8-5" /></>,
  video_generation: <><rect x="3" y="6" width="13" height="12" rx="2" /><path d="m16 10 5-3v10l-5-3v-4Z" /><path d="m8 9 4 3-4 3V9Z" /></>,
  image_generation: <><rect x="3" y="4" width="18" height="16" rx="2" /><circle cx="9" cy="9" r="1.5" /><path d="m4 17 5-5 3.5 3.5 2.5-2.5 5 5" /></>,
};

export function AgentRoleIcon({ nodeName }) {
  return (
    <svg className="agent-role-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      {ICONS[nodeName] || ICONS.intent_router}
    </svg>
  );
}
