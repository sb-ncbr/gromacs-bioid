import { Box, Tooltip, Typography } from "@mui/material";
import { CheckCircle, Error as ErrorIcon, Help as HelpIcon } from "@mui/icons-material";
import {FC, JSX} from "react";

export type TaskStatus = "unknown" | "ok" | "failed";

export interface Task {
    type: string; // short type like INPUT, CREATE, ...
    fullName: string; // full text from API
    status: TaskStatus;
    statusText: string; // the raw status string
}

interface TasksProgressBarProps {
    tasks: Task[];
}

const statusColor: Record<TaskStatus, string> = {
    unknown: "#9e9e9e", // grey
    ok: "#4caf50", // green
    failed: "#f44336" // red
};

const statusIcon: Record<TaskStatus, JSX.Element> = {
    unknown: <HelpIcon sx={{color: statusColor.unknown}}/>,
    ok: <CheckCircle sx={{color: statusColor.ok}}/>,
    failed: <ErrorIcon sx={{color: statusColor.failed}}/>
};

const TasksProgressBar: FC<TasksProgressBarProps> = ({ tasks }) => {
    // Determine line colors: green until first failure, grey after
    const getLineColor = (index: number) => {
        const prevStatuses = tasks.slice(0, index + 1).map(t => t.status);
        if (prevStatuses.every(s => s === "ok")) return statusColor.ok;
        return statusColor.unknown;
    };

    return (
        <Box sx={{ display: "flex", alignItems: "center", width: "100%", overflowX: "auto", pb: 2 }}>
            {tasks.map((task, index) => (
                <Box
                    key={task.type}
                    sx={{
                        display: "flex",
                        alignItems: "center",
                        flexShrink: 0,
                        minWidth: 80, // adjust for spacing
                    }}
                >
                    {/* Column for icon + label */}
                    <Box
                        sx={{
                            display: "flex",
                            flexDirection: "column",
                            alignItems: "center",
                        }}
                    >
                        <Tooltip
                            title={
                                <Box>
                                    <Typography variant="body2">{task.fullName}</Typography>
                                    <Typography variant="caption" color="text.secondary">
                                        {task.statusText || "Unknown status"}
                                    </Typography>
                                </Box>
                            }
                            arrow
                        >
                            <Box sx={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
                                {statusIcon[task.status]}
                            </Box>
                        </Tooltip>

                        <Typography
                            variant="caption"
                            sx={{ mt: 0.5, whiteSpace: "nowrap", userSelect: "none", color: "text.primary" }}
                        >
                            {task.type}
                        </Typography>
                    </Box>

                    {/* Horizontal line to the right of icon+label */}
                    {/* Show line for all tasks, including last */}
                    <Box
                        sx={{
                            height: "4px",
                            width: "50px",
                            backgroundColor: getLineColor(index),
                            mx: 1,
                            borderRadius: "2px",
                            visibility: index === tasks.length - 1 ? "hidden" : "visible"
                            // or to show last line too, remove this line
                        }}
                    />
                </Box>
            ))}
        </Box>
    );
};

export default TasksProgressBar;