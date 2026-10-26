/** Public surface of the run-header feature (SPEC.md §2, §3.1–3.2). */
export { RunHeader, default as RunHeaderDefault, type RunHeaderProps } from "./RunHeader";
export { ErrorBanner, default as ErrorBannerDefault, type ErrorBannerProps } from "./ErrorBanner";
export {
  pageName,
  pageTitle,
  formatSubmitted,
  metaLine,
  headerActions,
  bugReport,
  CANCEL_CONFIRM,
  type HeaderAction,
} from "./headerModel";
