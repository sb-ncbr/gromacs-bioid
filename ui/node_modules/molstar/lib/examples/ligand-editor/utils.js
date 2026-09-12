/**
 * Copyright (c) 2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 */
export class SingleTaskQueue {
    constructor() {
        this.queue = [];
    }
    run(fn) {
        if (this.queue.length < 2) {
            this.queue.push(fn);
        }
        else {
            this.queue[this.queue.length - 1] = fn;
        }
        if (this.queue.length === 1) {
            this.next();
        }
    }
    async next() {
        while (this.queue.length > 0) {
            try {
                const fn = this.queue[0];
                await fn();
            }
            catch (e) {
                console.error('Error in SingleTaskQueue execution:', e);
            }
            finally {
                this.queue.shift();
            }
        }
    }
}
