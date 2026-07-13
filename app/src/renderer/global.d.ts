import type { PressFApi } from "../main/preload";

declare module "*.png" {
  const src: string;
  export default src;
}

declare global {
  interface Window {
    pressf: PressFApi;
  }
}
