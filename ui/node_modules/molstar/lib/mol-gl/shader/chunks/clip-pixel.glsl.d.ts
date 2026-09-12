export declare const clip_pixel = "\n#if defined(dClipVariant_pixel) && dClipObjectCount != 0\n    if (clipTest(vModelPosition))\n        discard;\n#endif\n";
