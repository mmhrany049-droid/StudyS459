# سیستم کتاب و Import — نسخه ۱

## اصل
ساختار کتاب data-driven است.

Config باید بتواند تعریف کند:
- metadata
- hierarchy
- node types
- order
- test types
- difficulty levels
- special sections
- question mappings

## Leaf
کوچک‌ترین واحد قابل انتخاب باید قابل تشخیص باشد.

## Multi-topic
Question می‌تواند به چند Node متصل باشد.

## Stable IDs
book.stable_key و question.stable_key پایدار باشند.

## Import
فاز اول JSON/config.
فاز بعد package/ZIP شامل:
- metadata
- nodes
- test sets
- questions
- answer keys
- optional images

## Validation
- parent همان book باشد.
- cycle ممنوع.
- question و test set متعلق به همان book باشند.
- stable key تکراری نباشد.
- order معتبر باشد.
- sequence_no یکتا و صعودی در هر test set باشد.

## Activation
کاربر می‌تواند کتاب را فعال/غیرفعال کند.
غیرفعال کردن نباید history را پاک کند.
