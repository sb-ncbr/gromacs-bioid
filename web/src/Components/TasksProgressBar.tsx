import { Box, Tooltip, Typography, CircularProgress } from "@mui/material";
import { CheckCircle, Error as ErrorIcon, Help as HelpIcon } from "@mui/icons-material";
import { FC, JSX } from "react";

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
    unknown: <HelpIcon sx={{ color: statusColor.unknown }} />,
    ok: <CheckCircle sx={{ color: statusColor.ok }} />,
    failed: <ErrorIcon sx={{ color: statusColor.failed }} />,
    inprogress: <CircularProgress size={20} sx={{ color: statusColor.inprogress }} />
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
                            alignItems: "center",
                            flexShrink: 0,
                            minWidth: 80,
                        }}
                    >
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
                                    {statusIcon[displayStatus]}
                                </Box>
                            </Tooltip>

                            <Typography
                                variant="caption"
                                sx={{ mt: 0.5, whiteSpace: "nowrap", userSelect: "none", color: "text.primary" }}
                            >
                                {task.type}
                            </Typography>
                        </Box>

                        <Box
                            sx={{
                                height: "4px",
                                width: "50px",
                                backgroundColor: getLineColor(index),
                                mx: 1,
                                borderRadius: "2px",
                                visibility: index === tasks.length - 1 ? "hidden" : "visible"
                            }}
                        />
                    </Box>
                );
            })}
        </Box>
    );
};

export default TasksProgressBar;
