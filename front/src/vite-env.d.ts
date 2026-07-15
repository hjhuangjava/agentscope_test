/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_BRIDGE_USER_ID?: string;
  readonly VITE_BRIDGE_MODEL_URL?: string;
  readonly VITE_BRIDGE_MODEL_NAME?: string;
  readonly VITE_BRIDGE_MODEL_TOKEN?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
