import React from "react";

export default function Composer({ value, onChange, onSend }) {
  return (
    <footer className="composer">
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            onSend();
          }
        }}
        placeholder="Message… Enter to send, Shift+Enter for newline"
      />
      <button className="primary send" onClick={onSend}>
        Send
      </button>
    </footer>
  );
}
