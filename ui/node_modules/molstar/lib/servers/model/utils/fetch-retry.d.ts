/**
 * Copyright (c) 2018-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 * @author Adam Midlik <midlik@gmail.com>
 */
import fetch, { Response } from 'node-fetch';
export declare function fetchRetry(url: string, timeout: number, retryCount: number, onRetry?: () => void): Promise<Response>;
/** Like `fetch` but supports Google Cloud Storage (gs://) protocol. */
export declare function wrapFetch(url: string, init?: fetch.RequestInit): Promise<Response>;
