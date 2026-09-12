"use strict";
/**
 * Copyright (c) 2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.ErrorContext = void 0;
class ErrorContext {
    constructor() {
        this.errors = Object.create(null);
    }
    get(tag) {
        var _a;
        return (_a = this.errors[tag]) !== null && _a !== void 0 ? _a : [];
    }
    add(tag, error) {
        if (tag in this.errors && Array.isArray(this.errors[tag])) {
            this.errors[tag].push(error);
        }
        else {
            this.errors[tag] = [error];
        }
    }
    clear(tag) {
        delete this.errors[tag];
    }
}
exports.ErrorContext = ErrorContext;
