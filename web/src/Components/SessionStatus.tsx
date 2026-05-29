import React from "react";

interface SessionStatusProps {
    children: string;
}

const SessionStatus: React.FC<SessionStatusProps> = ({ children }) => {
    const color = children === "completed" ? "green" : "orange";

    return <span style={{ color }}>{children}</span>;
};

export default SessionStatus;