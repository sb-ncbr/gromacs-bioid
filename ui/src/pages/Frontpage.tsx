import UploadForm from "../features/frontpage/UploadForm";
import Recents from "../features/frontpage/Recents";
import Examples from "../features/frontpage/Examples";

/**
 * Frontpage: upload flow + IP-bound recent annotations.
 * Two columns on xl (form 7 / recents 5), stacked on smaller viewports.
 * Below: landing "Example analyses" cards (v3.137, /runs/examples).
 */
export default function Frontpage() {
  return (
    <div className="flex flex-col gap-8">
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
        <div className="xl:col-span-7">
          <UploadForm />
        </div>
        <div className="xl:col-span-5">
          <Recents />
        </div>
      </div>
      <Examples />
    </div>
  );
}
