// ShowComplete.tsx
import { FC } from "react";

interface Props {
    uuid: string;
}

const ShowComplete: FC<Props> = ({ uuid }) => {
    return <div>ShowComplete page — UUID: {uuid}</div>;
};

export default ShowComplete;
