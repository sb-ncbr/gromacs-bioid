import { Box, Tooltip, Typography, CircularProgress } from "@mui/material";
import { CheckCircle, Error as ErrorIcon, Help as HelpIcon } from "@mui/icons-material";
import React, { FC, JSX } from "react";

export type TaskStatus = "unknown" | "ok" | "failed" | "inprogress";

export interface Task {
    type: string;
    fullName: string;
    status: TaskStatus;
    statusText: string;
}

interface TasksProgressBarProps {
    tasks: Task[];
}

const statusColor: Record<TaskStatus, string> = {
    unknown: "#9e9e9e",      // grey
    ok: "#4caf50",           // green
    failed: "#f44336",       // red
    inprogress: "#2196f3" // blue
};

const statusIcon: Record<TaskStatus, JSX.Element> = {
    unknown: <HelpIcon sx={{ color: statusColor.unknown, fontSize: "4rem" }} />,
    ok: <CheckCircle sx={{ color: statusColor.ok, fontSize: "4rem" }} />,
    failed: <ErrorIcon sx={{ color: statusColor.failed, fontSize: "4rem" }} />,
    inprogress: <CircularProgress size={40} sx={{ color: statusColor.inprogress, fontSize: "4rem" }} />,
};

const TasksProgressBar: FC<TasksProgressBarProps> = ({ tasks }) => {

    const getDisplayStatus = (task: Task, index: number): TaskStatus => {
        const anyFailed = tasks.some(t => t.status === "failed");
        const anyOk = tasks.some(t => t.status === "ok");

        if (task.status === "unknown") {
            // in-progress if at least one OK and no failed tasks
            if (anyOk && !anyFailed) {
                const lastOkIndex = tasks.map(t => t.status).lastIndexOf("ok");
                if (index > lastOkIndex) return "inprogress";
            }
        }

        return task.status;
    };

    const getLineColor = (index: number) => {
        const prevStatuses = tasks.slice(0, index + 1).map((t, i) => getDisplayStatus(t, i));
        // Only count actual OK tasks, not in-progress, for line coloring
        if (prevStatuses.every(s => s === "ok")) {
            return statusColor.ok;
        }

        const currentStatus = prevStatuses[prevStatuses.length - 1];
        if (currentStatus === "failed") {
            return statusColor.failed; // red
        }

        if (currentStatus === "inprogress") {
            return statusColor.inprogress; // red
        }

        return statusColor.unknown;
    };

    return (
        <Box sx={{ display: "flex", alignItems: "center", width: "100%", overflowX: "auto", pb: 2 }}>
            {tasks.map((task, index) => {
                const displayStatus = getDisplayStatus(task, index);
                return (
                    <Box
                        key={task.type}
                        sx={{
                            display: "flex",
                            flexDirection: "column",
                            alignItems: "center",
                            flex: 1,
                            minWidth: 0,
                            px: 1,
                            py: 2,
                            borderRadius: 2,
                            transition: "background-color 0.2s ease",
                            "&:hover": {
                                backgroundColor: displayStatus === "ok" ? "rgba(0,0,0,0.08)" : "transparent", // gray tint on hover
                            },
                        }}
                    >
                        <Tooltip
                            title={
                                <Box>
                                    <Typography variant="body1">{task.fullName}</Typography>
                                    <Typography variant="caption" color="text.secondary">
                                        {task.statusText || "Unknown status"}
                                    </Typography>
                                </Box>
                            }
                            arrow
                        >
                            <Box
                                sx={{
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    width: "100%",
                                    py: 3,
                                }}
                            >
                                {statusIcon[displayStatus]}
                            </Box>
                        </Tooltip>

                        <Typography
                            variant="h6" // bigger text (you can also use variant="h5" for even larger)
                            sx={{
                                mt: 1,
                                whiteSpace: "pre-line",
                                userSelect: "none",
                                color: "text.primary",
                                textAlign: "center",
                                fontWeight: 500,
                            }}
                        >
                            {task.fullName.replace(/\\n/g, "\n")}
                        </Typography>

                        {/* line connecting tasks */}
                        {index < tasks.length && (
                            <Box
                                sx={{
                                    height: "8px",
                                    width: "100%",
                                    backgroundColor: getLineColor(index),
                                    mt: 2,
                                    borderRadius: "3px",
                                }}
                            />
                        )}
                    </Box>
                );

            })}
        </Box>
    );
};

export default TasksProgressBar;
