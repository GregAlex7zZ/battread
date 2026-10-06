# API reference

The implemented public surface includes generic delimited and canonical
Parquet, Bio-Logic and Neware reading, inspection, streaming chunks, canonical writing and
conversion, schema constants, validation, and merging.

Bio-Logic MPR inspection reads bounded metadata; MPT inspection samples text.
Neither loads all measurement values. `read()` collects the full result, while
`iter_read()` and `convert()` support incremental consumption; see
[large files](../user-guide/large-files.md).

    from battread import (
        CANONICAL_COLUMNS,
        SCHEMA_VERSION,
        convert,
        detect_format,
        inspect,
        is_standardized,
        iter_read,
        merge,
        read,
        write,
    )

## Reading

::: battread.api.detect_format

::: battread.api.inspect

::: battread.api.read

::: battread.api.iter_read

## Writing and conversion

::: battread.output.write

::: battread.output.convert

## Validation predicate

::: battread.validation.is_standardized

## Merge

::: battread.merge.merge

Domain exceptions are available from **battread.exceptions**, and warning
categories are available from **battread.warnings**.
