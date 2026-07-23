# Function Title Cache-Key Design

## Goal

Ensure generated function titles remain globally unique after title
disambiguation, including when Word render-cache entries already exist.

## Cause

The render cache key currently uses only source file, function name, and
function body. A cached function block created before title disambiguation is
therefore replayed even after the final title changes.

## Design

The cache key will include the resolved `file_context.function_title`. All
render entry points will pass this value after project title registration. A
title change will then select a new cache entry and force a fresh render. The
module tables and body already obtain their title from the same registered
value.

## Verification

Unit tests will assert that a changed resolved title changes the cache key,
while unchanged inputs remain stable.
