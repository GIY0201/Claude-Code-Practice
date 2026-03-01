import { useState, useRef, useEffect } from "react";
import { useDroneState } from "../hooks/useDroneState";
import type { ChatMessage, ChatIntent } from "../types";

/** intent별 메시지 스타일 */
function intentStyle(intent?: ChatIntent): string {
  switch (intent) {
    case "FLIGHT_PLAN":
      return "border-l-2 border-blue-500 pl-2";
    case "ALTITUDE_CHANGE":
    case "SPEED_CHANGE":
      return "border-l-2 border-yellow-500 pl-2";
    case "HOLD":
    case "RETURN_TO_BASE":
      return "border-l-2 border-orange-500 pl-2";
    case "SET_NOTAM":
      return "border-l-2 border-red-500 pl-2";
    case "BRIEFING":
      return "border-l-2 border-green-500 pl-2";
    default:
      return "";
  }
}

/** intent 라벨 */
function intentLabel(intent?: ChatIntent): string | null {
  const labels: Record<string, string> = {
    FLIGHT_PLAN: "Flight Plan",
    ALTITUDE_CHANGE: "Altitude",
    SPEED_CHANGE: "Speed",
    HOLD: "Hold",
    RETURN_TO_BASE: "RTL",
    SET_NOTAM: "NOTAM",
    BRIEFING: "Briefing",
  };
  return intent ? labels[intent] ?? null : null;
}

function ChatPanel() {
  const chatMessages = useDroneState((s) => s.chatMessages);
  const chatOpen = useDroneState((s) => s.chatOpen);
  const chatLoading = useDroneState((s) => s.chatLoading);
  const chatSessionId = useDroneState((s) => s.chatSessionId);
  const addChatMessage = useDroneState((s) => s.addChatMessage);
  const setChatOpen = useDroneState((s) => s.setChatOpen);
  const setChatLoading = useDroneState((s) => s.setChatLoading);
  const clearChat = useDroneState((s) => s.clearChat);

  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 새 메시지 시 하단 스크롤
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  /** 메시지 전송 */
  const handleSend = async (text?: string) => {
    const message = (text ?? input).trim();
    if (!message || chatLoading) return;

    // 사용자 메시지 추가
    addChatMessage({
      role: "user",
      content: message,
      timestamp: Date.now(),
    });
    setInput("");
    setChatLoading(true);

    try {
      const resp = await fetch("/api/chat/message", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message,
          session_id: chatSessionId,
        }),
      });

      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      const data = await resp.json();

      addChatMessage({
        role: "assistant",
        content: data.message,
        timestamp: Date.now(),
        intent: data.intent,
        requiresConfirmation: data.requires_confirmation,
        action: data.action,
      });
    } catch (err) {
      addChatMessage({
        role: "assistant",
        content: `오류가 발생했습니다: ${err instanceof Error ? err.message : "Unknown error"}`,
        timestamp: Date.now(),
      });
    } finally {
      setChatLoading(false);
    }
  };

  /** 브리핑 요청 */
  const handleBriefing = async () => {
    if (chatLoading) return;

    addChatMessage({
      role: "user",
      content: "상황 브리핑 요청",
      timestamp: Date.now(),
    });
    setChatLoading(true);

    try {
      const drones = useDroneState.getState().drones;
      const activeDrones = Array.from(drones.values()).filter(
        (d) => d.status === "AIRBORNE"
      ).length;
      const holdingDrones = Array.from(drones.values()).filter(
        (d) => d.status === "HOLDING"
      ).length;

      const resp = await fetch(
        `/api/chat/briefing?active_drones=${activeDrones}&holding_drones=${holdingDrones}`,
        { method: "POST" }
      );

      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      const data = await resp.json();

      addChatMessage({
        role: "assistant",
        content: data.briefing,
        timestamp: Date.now(),
        intent: "BRIEFING",
      });
    } catch (err) {
      addChatMessage({
        role: "assistant",
        content: `브리핑 생성 실패: ${err instanceof Error ? err.message : "Unknown error"}`,
        timestamp: Date.now(),
      });
    } finally {
      setChatLoading(false);
    }
  };

  /** 키보드 이벤트 */
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // ── 접힌 상태: 토글 버튼만 ──
  if (!chatOpen) {
    return (
      <button
        onClick={() => setChatOpen(true)}
        className="ui-overlay bottom-4 left-4 w-12 h-12 rounded-full bg-blue-600 hover:bg-blue-700 text-white shadow-lg flex items-center justify-center transition-colors"
        title="AI Controller"
      >
        <svg
          className="w-6 h-6"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
          />
        </svg>
      </button>
    );
  }

  // ── 열린 상태: 채팅 패널 ──
  return (
    <div className="ui-overlay bottom-4 left-4 w-96 max-h-[calc(100vh-100px)] bg-gray-800/95 rounded-lg shadow-xl border border-gray-700 flex flex-col">
      {/* 헤더 */}
      <div className="px-4 py-2.5 bg-gray-900/50 flex items-center justify-between border-b border-gray-700 shrink-0 rounded-t-lg">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-blue-400" />
          <h2 className="text-xs font-semibold text-gray-300 uppercase tracking-wider">
            AI Controller
          </h2>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setChatOpen(false)}
            className="text-gray-500 hover:text-gray-300 p-1"
            title="Close"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* 메시지 영역 */}
      <div className="flex-1 overflow-y-auto max-h-80 min-h-[120px]">
        {chatMessages.length === 0 ? (
          <div className="px-4 py-6 text-center text-gray-500 text-xs">
            <p>SkyMind AI Controller</p>
            <p className="mt-1 text-gray-600">
              자연어로 드론을 관제하세요.
            </p>
            <p className="mt-2 text-gray-600 text-[10px]">
              예: "홍대에서 강남까지 배송", "드론 3번 고도 올려"
            </p>
          </div>
        ) : (
          chatMessages.map((msg, i) => (
            <MessageBubble key={i} message={msg} />
          ))
        )}
        {chatLoading && (
          <div className="px-4 py-2 text-xs text-gray-500 flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
            응답 대기 중...
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* 입력 영역 */}
      <div className="px-3 py-2.5 border-t border-gray-700 shrink-0">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="관제 명령 입력..."
            disabled={chatLoading}
            className="flex-1 bg-gray-700 text-white rounded px-3 py-1.5 text-xs border border-gray-600 focus:border-blue-500 focus:outline-none disabled:opacity-50 placeholder-gray-500"
          />
          <button
            onClick={() => handleSend()}
            disabled={chatLoading || !input.trim()}
            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white rounded text-xs font-medium transition-colors"
          >
            Send
          </button>
        </div>
      </div>

      {/* 퀵 액션 */}
      <div className="px-3 py-2 border-t border-gray-700/50 flex gap-1.5 shrink-0 rounded-b-lg">
        <QuickButton label="Briefing" onClick={handleBriefing} disabled={chatLoading} />
        <QuickButton
          label="Hold All"
          onClick={() => handleSend("전체 드론 홀딩")}
          disabled={chatLoading}
        />
        <QuickButton
          label="Clear"
          onClick={clearChat}
          variant="danger"
        />
      </div>
    </div>
  );
}

/** 메시지 버블 */
function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const label = intentLabel(message.intent);

  return (
    <div
      className={`px-4 py-2 border-t border-gray-700/30 ${
        isUser ? "bg-gray-700/20" : "bg-gray-800/50"
      }`}
    >
      <div className="flex items-center gap-2 mb-1">
        <span
          className={`text-[10px] font-semibold uppercase tracking-wider ${
            isUser ? "text-blue-400" : "text-green-400"
          }`}
        >
          {isUser ? "You" : "ATC"}
        </span>
        {label && (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-600/50 text-gray-400">
            {label}
          </span>
        )}
        <span className="text-[10px] text-gray-600 ml-auto">
          {new Date(message.timestamp).toLocaleTimeString("ko-KR", {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
      </div>
      <div
        className={`text-xs text-gray-300 whitespace-pre-wrap leading-relaxed ${intentStyle(
          message.intent
        )}`}
      >
        {message.content}
      </div>
    </div>
  );
}

/** 퀵 액션 버튼 */
function QuickButton({
  label,
  onClick,
  disabled,
  variant = "default",
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  variant?: "default" | "danger";
}) {
  const base =
    "flex-1 py-1 rounded text-[10px] font-medium uppercase tracking-wider transition-colors disabled:opacity-40";
  const style =
    variant === "danger"
      ? "bg-gray-700 hover:bg-red-900/50 text-gray-400 hover:text-red-300"
      : "bg-gray-700 hover:bg-gray-600 text-gray-400 hover:text-gray-200";

  return (
    <button onClick={onClick} disabled={disabled} className={`${base} ${style}`}>
      {label}
    </button>
  );
}

export default ChatPanel;
