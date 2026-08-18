export interface FrontendConfig {
  api_base_url: string
  max_upload_bytes: number
}

export const appConfig = (globalThis as typeof globalThis & { __BOULDER_FRAME_CONFIG__: FrontendConfig })
  .__BOULDER_FRAME_CONFIG__
