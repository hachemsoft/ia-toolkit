# <Project name>

<One or two sentences: the business scope of this repo and why it exists.>

## Language

**Grain**:
What one row of a table or result represents, stated before any join or aggregation.
_Avoid_: granularity, level of detail

**Key**:
Column or combination of columns that identifies a row at the declared grain.
_Avoid_: identifier, technical id

**Source**:
Data as delivered by the originating system, without transformation.
_Avoid_: raw, landing

**Staging**:
First transformation layer: renaming, typing, light cleaning, grain unchanged.
_Avoid_: stg, preparation

**Intermediate**:
Business transformation reused by several marts.
_Avoid_: int, technical layer

**Mart**:
Final table intended for a use: reporting, exposure, model. Grain documented.
_Avoid_: datamart, final table, business view

**Dimension**:
Descriptive attributes of an entity, linked to facts by a key.
_Avoid_: reference data, lookup table

**Fact**:
Measures at the grain of an event, linked to dimensions.
_Avoid_: fact table, transactions

**Partition**:
Physical split of a table by a column, filtered to reduce bytes read.
_Avoid_: shard, segment

**Clustering**:
Physical sorting by columns within a table, useful for frequent filters and joins.
_Avoid_: index, sort

**Incremental**:
Processing of new data only, according to a key and a freshness rule.
_Avoid_: delta, append

**Replay**:
Rebuilding a period of data; its behaviour is defined before choosing incremental.
_Avoid_: backfill, full refresh (the latter names the command, not the intent)
