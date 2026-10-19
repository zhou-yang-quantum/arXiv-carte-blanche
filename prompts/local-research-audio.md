# Audio annotation instructions

Also return math_pronunciations as a list: one object with latex and spoken fields for each
distinct math expression in the item titles, summaries, backgrounds, and relevance
sections. latex must copy the exact expression including its delimiters. spoken
must be a faithful, natural English reading of that exact expression, as a
physicist would say it aloud. Preserve grouping, fractions, indices, exponents,
operators, relations, limits, sums, and qualifiers. For example, $x^2$ is "x
squared", not "x caret two"; $I(A:C|B)$ is "the conditional mutual information
between A and C given B"; a fraction should say what is divided by what. Do not
substitute an interpretation, approximation, or new result for the expression.
Include every distinct expression exactly once; use an empty list if there are
none or status is insufficient. This small list supplies an audio version by
replacing only math; do not duplicate or paraphrase the digest's prose.

Use the reader's preferred compact math pronunciation. In a QEC context,
$[[4,2,2]]$ is "four two two": do not read the brackets, insert "comma", or
expand the code parameters into an explanation. Let the surrounding prose
establish that this is QEC code notation. Apply the same convention to other
quantum-code parameter triples while preserving the values. Read
$c_j$ as "C sub J" and $c_{j+1}$ as "C sub (J plus one)": say "sub" before
the subscript and keep a multiword index together. Accordingly, read
$F_j = c^\dagger_j + c^\dagger_{j+1}$ as "F sub J equals C sub J dagger plus
C sub (J plus one) dagger": put each subscript before "dagger", omit "at site",
and keep the entire J plus one index together so its addition is not mistaken
for a separate term. Copy the actual source expression exactly in latex,
even when its spacing or superscript/subscript order differs from this example.

For single-letter mathematical symbols, including $N$ and $\mathcal{N}$,
prefer simply "N" when the surrounding context identifies the symbol, as it
usually does: "large N" and "N equals four super Yang Mills" for
$\mathcal{N}=4$ super Yang–Mills. When context is insufficient, say "capital N".
Apply the same principle to other letters. Do not routinely spell out case or
font styling such as "calligraphic" or "script". Include a typographic
distinction only when the listener needs it to distinguish quantities that
would otherwise have the same spoken name. Preserve indices and other
mathematical structure even when simplifying the letter's name.

Give equations a clear rhythm by inserting [p] for a short pause between
meaningful math units, especially around relations and between additive terms.
Use parentheses in spoken only to group words read slightly faster as one unit;
they are timing controls and are not said aloud. The preferred reading above is
"F sub J [p] equals [p] C sub J dagger [p] plus [p] C sub (J plus one) dagger".
Keep individual variables, indices, and operators connected within their units;
avoid pausing between every word. Use these controls only in spoken, never in
the digest prose or latex field. Groups must be nonempty, cannot nest, and
cannot contain [p]. Write semantic parentheses in words when they must be heard.
Apart from [p] and these grouping parentheses, spoken must remain plain English,
without TeX, SSML, or other markup.

Also return phrase_groups, a list of groups for technical terminology in the
titles, summaries, backgrounds, and relevance sections. Each entry is a list
of one or more exact source-text parts. Joining its parts with one space must
reproduce a contiguous phrase from the digest exactly, including any Markdown
or math delimiters. One part means speak the whole phrase as one continuous
unit at normal speed; multiple parts add a short pause only between those parts.
The renderer keeps each part in one synthesis request, without splitting it at
the ordinary text chunk limit, and treats word-joining hyphens and name-separating dashes
inside the phrase as word joins. These annotations affect only audio delivery;
do not alter the written title or prose to force a pronunciation. The daily
overview, reading-order note, and day-level synthesis are outside these narrated
sections: do not annotate phrases or equations that occur only there.

Use the paper's meaning to identify complete terminology and the scope of
shared modifiers. Avoid colloquial list or aside intonation inside a technical
phrase. For example, in "Large $N$ Vector and SYK-like Models", large N can
modify both model families. After confirming this from the paper, use either
["Large $N$ Vector and SYK-like Models"] for continuous delivery or
["Large $N$", "Vector and SYK-like Models"] for a short pause that preserves
the shared modifier. Do not pause after "Vector" as if large N modified only
the vector models. This example illustrates the method; apply the actual
source's meaning rather than assuming the same scope in every paper.

Treat multi-name terms such as "Sachdev–Ye–Kitaev" as one unit: use
["Sachdev–Ye–Kitaev"] with the source's exact dash spelling. Prefer continuous
delivery, or at most equally short separations between the names; do not read
the dashes as parenthetical interruptions. Extend this treatment to multiword
physics and mathematics terms, named constructions, and compound modifiers
whose words together name one concept. Grouping is not a request to accelerate
or overemphasize all jargon. Avoid grouping whole sentences or paragraphs.

Return only necessary, nonoverlapping phrases, each at most 400 characters,
with up to eight nonempty parts. Never cut a math expression between parts or
at the phrase boundary. If a phrase includes inline math, its words come from
math_pronunciations but its phrase grouping takes precedence over internal math
timing controls. An exact phrase group applies to every occurrence of that
source string in the reading sections. Use [] when no grouping is needed or
status is insufficient. Review both equation readings and terminology grouping
against the source before returning the final JSON.
