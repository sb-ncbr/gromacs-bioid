/**
 * Copyright (c) 2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Sebastian Bittrich <sebastian.bittrich@rcsb.org>
 */
export declare function getSchema(): {
    openapi: string;
    info: {
        version: string;
        title: string;
        description: string;
    };
    tags: {
        name: string;
    }[];
    paths: {
        [x: string]: {
            get: {
                tags: string[];
                summary: string;
                operationId: string;
                parameters: {
                    $ref: string;
                }[];
                responses: {
                    200: {
                        description: string;
                        content: {
                            'application/json': {
                                schema: {
                                    $ref: string;
                                };
                            };
                        };
                    };
                };
            };
        };
    };
    components: {
        schemas: {
            prediction: {
                type: string;
                properties: {
                    planePoint1: {
                        type: string;
                        items: {
                            type: string;
                        };
                        minItems: number;
                        maxItems: number;
                        description: string;
                    };
                    planePoint2: {
                        type: string;
                        items: {
                            type: string;
                        };
                        minItems: number;
                        maxItems: number;
                        description: string;
                    };
                    normalVector: {
                        type: string;
                        items: {
                            type: string;
                        };
                        minItems: number;
                        maxItems: number;
                        description: string;
                    };
                    centroid: {
                        type: string;
                        items: {
                            type: string;
                        };
                        minItems: number;
                        maxItems: number;
                        description: string;
                    };
                    radius: {
                        type: string;
                        description: string;
                    };
                };
            };
        };
        parameters: {
            id: {
                name: string;
                in: string;
                description: string;
                required: boolean;
                schema: {
                    default: string;
                    type: string;
                };
                style: string;
            };
            assemblyId: {
                name: string;
                in: string;
                description: string;
                required: boolean;
                schema: {
                    default: string;
                    type: string;
                };
                style: string;
            };
            numberOfSpherePoints: {
                name: string;
                in: string;
                description: string;
                required: boolean;
                schema: {
                    type: string;
                    minimum: number;
                    maximum: number;
                    default: number;
                };
                style: string;
            };
            stepSize: {
                name: string;
                in: string;
                description: string;
                required: boolean;
                schema: {
                    type: string;
                    minimum: number;
                    maximum: number;
                    default: number;
                };
                style: string;
            };
            minThickness: {
                name: string;
                in: string;
                description: string;
                required: boolean;
                schema: {
                    type: string;
                    minimum: number;
                    maximum: number;
                    default: number;
                };
                style: string;
            };
            maxThickness: {
                name: string;
                in: string;
                description: string;
                required: boolean;
                schema: {
                    type: string;
                    minimum: number;
                    maximum: number;
                    default: number;
                };
                style: string;
            };
            asaCutoff: {
                name: string;
                in: string;
                description: string;
                required: boolean;
                schema: {
                    type: string;
                    minimum: number;
                    maximum: number;
                    default: number;
                };
                style: string;
            };
            adjust: {
                name: string;
                in: string;
                description: string;
                required: boolean;
                schema: {
                    type: string;
                    minimum: number;
                    maximum: number;
                    default: number;
                };
                style: string;
            };
            tmdetDefinition: {
                name: string;
                in: string;
                description: string;
                required: boolean;
                schema: {
                    type: string;
                    default: boolean;
                };
                style: string;
            };
        };
    };
};
export declare const shortcutIconLink = "<link rel='shortcut icon' href='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAMAAABEpIrGAAAABGdBTUEAALGPC/xhBQAAAAFzUkdCAK7OHOkAAAAnUExURQAAAMIrHrspHr0oH7soILonHrwqH7onILsoHrsoH7soH7woILwpIKgVokoAAAAMdFJOUwAQHzNxWmBHS5XO6jdtAmoAAACZSURBVDjLxZNRCsQgDAVNXmwb9f7nXZEaLRgXloXOhwQdjMYYwpOLw55fBT46KhbOKhmRR2zLcFJQj8UR+HxFgArIF5BKJbEncC6NDEdI5SatBRSDJwGAoiFDONrEJXWYhGMIcRJGCrb1TOtDahfUuQXd10jkFYq0ViIrbUpNcVT6redeC1+b9tH2WLR93Sx2VCzkv/7NjfABxjQHksGB7lAAAAAASUVORK5CYII=' />";
