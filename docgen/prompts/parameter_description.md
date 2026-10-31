# Rules for writing API parameter descriptions

Describe what one parameter means, so a developer knows what value to send. The reader already sees the parameter's name, type, location and whether it's required, in the table next to your description.

1. Write a short noun phrase, not a sentence. For example: `The playlist's id`, `Only recordings of works by this composer`, `Maximum number of results`. Do not start with a verb such as "Specifies" or "Is used to".

2. Keep it short. Aim for under 12 words. Use a second phrase only when it adds something the developer needs, such as accepted values shown in the examples.

3. Say what the value means, not what type it is. The type is already shown. Write `The recording to add`, not `An integer`.

4. For filters, say what they narrow down. Start query filters with `Only`, for example `Only recordings from this musical period`.

5. For true/false parameters, say what `true` means, and start with the value. For example: `true for only books not currently on loan`. This tells the developer exactly what to send.

6. Use plain English and British spelling. No jargon, vague expressions or marketing language. Write ID in capitals in sentences. Only write `id`, in code font, when naming the field itself.

7. No full stop. Parameter descriptions are phrases in a table, so they end without punctuation.

8. Do not repeat the parameter's name as its whole description. `name: The name` tells the reader nothing.

9. Do not invent behaviour. This is the most important rule. Only describe what the facts supplied support, including the endpoint's summary, other parameters, responses and examples. Never invent default values, limits, formats, accepted values or validation rules that the facts don't state.

10. Handle missing information conservatively. If the facts do not support an accurate description, return exactly this phrase and nothing else: `Insufficient information to describe this parameter`

11. Return only the description. No heading, explanation, introductory phrase, quotation marks or commentary.
