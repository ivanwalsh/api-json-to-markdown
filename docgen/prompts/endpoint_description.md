# Rules for writing API endpoint descriptions

Brief the reader on what the endpoint does. Assume the reader is a developer who needs to understand its purpose quickly before deciding whether to use it. The description should explain the endpoint's primary function, not repeat its parameters or document every implementation detail.

Follow these rules:

1. Start with an action verb. Use the present tense. Choose a verb that accurately describes the operation, for example:
   - `Returns` for retrieving or searching for resources.
   - `Creates` for creating a resource.
   - `Adds` for adding something to a resource.
   - `Removes` for removing something.
   - `Updates` for modifying an existing resource.
   - `Ends` for closing or completing something, such as a loan.

2. Keep it short. Write one sentence. Use two sentences only when an additional detail is necessary to explain an important aspect of the operation.

3. Describe the primary outcome. Explain what the endpoint returns, creates, adds, removes or changes. Focus on what the developer needs to know to understand its purpose.

4. Include important behaviour when documented. Mention details that materially affect how the endpoint works, such as:
   - Whether a search supports filters.
   - Whether a resource includes related items.
   - Whether items are returned in a particular order.
   - Whether an operation creates an empty resource.
   - Whether an item is added to the beginning or end of a collection.
   - Whether removing an item changes the position of other items.

5. Use plain English. Prefer familiar words and straightforward sentence structures. Avoid unnecessary technical jargon, vague expressions and marketing language such as "seamlessly", "powerful", "robust" or "intuitive".

6. Use present tense and active voice. Write `Returns a recording`, not `Will return a recording` or `A recording is returned`.

7. Use consistent spelling. Use British English throughout, including spelling such as `catalogue` rather than `catalog`.

8. Use a full stop. Every description must end with exactly one full stop. Do not leave the description without punctuation.

9. Do not repeat information unnecessarily. Do not simply restate the endpoint name, HTTP method, path, summary or parameter descriptions. Explain the operation's purpose instead.

10. Do not invent behaviour. This is the most important rule. Only describe behaviour supported by the facts supplied, which include the summary, parameters, responses and response examples. Never assume or invent:
    - Rate limits or request restrictions.
    - Authentication requirements or permissions.
    - Validation rules not documented in the source.
    - Side effects or changes to other resources.
    - Default behaviour not explicitly stated.
    - Error handling or response behaviour not documented.
    - Performance, reliability or availability characteristics.

11. Do not turn assumptions into facts. A behaviour that seems technically likely is not necessarily how the API works. For example, do not assume that deleting an item also deletes its associated resource.

12. Handle missing information conservatively. If the facts do not support an accurate description, do not guess or fill in the gaps. Return exactly this sentence and nothing else: `Insufficient information to describe this endpoint.` A reviewer will see it and add the missing detail.

13. Return only the description. Do not include a heading, explanation, introductory phrase, quotation marks or commentary. The output must be ready to insert directly into the API specification.

14. Check the result before returning it. Confirm that the description:
    - Starts with an appropriate action verb.
    - Accurately reflects the documented behaviour.
    - Contains no unsupported claims.
    - Uses plain English and present tense.
    - Ends with exactly one full stop.
