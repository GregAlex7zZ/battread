# API reference

The implemented public surface includes generic delimited and canonical
Parquet, Bio-Logic and Neware reading, inspection, streaming chunks, canonical writing and
conversion, schema constants, validation, and merging.

Bio-Logic MPR inspection loads the complete backend table; see the reader guide
for its memory limitation. MPT inspection samples text without loading the
complete acquisition.

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
