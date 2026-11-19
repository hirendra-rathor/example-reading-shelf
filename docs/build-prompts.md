# Reading Shelf prompts used by Codex

## 1. Capture and track reading

```text
I would like to develop a full-stack application called Reading Shelf. When I
come across an article I want to read later, I’d like to paste in the link,
give it a title, and save it. Then, when I have time to read, I can open my
library and click the title to get back to the original article.

I often forget why I saved something, so I’d like a place to leave myself a
note. One note per article is plenty, as long as I can edit it later. I’d also
like to keep track of what I’ve started reading. I think “To read”, “Reading”,
and “Read” would cover it. If I leave a note and mark an article “Reading”,
I’d expect to see that note and status again after I restart the app.

I’d like to use Flask to serve the page and a JSON API. Plain HTML, CSS, and
JavaScript are fine for the page, and I’d like to keep my library in a local
SQLite database.

Give me a design proposal [use $ca-design-proposal].
```

## 2. Organize the library

```text
Now I’d like the app to support organizing the articles I’ve already saved.
Could you help me figure out how collections would work? I’d like to name them
myself. For example, I might make one called “Food and cooking” and another
called “Weekend reading”. Sometimes I’ll want to put the same article in both.

Say I open that article from “Food and cooking” and change my note. When I
open it later from “Weekend reading”, I’d expect to see the note I just wrote.
And if I decide it doesn’t belong in “Food and cooking” anymore, I’d like to
take it out of that collection and still find it in “Weekend reading” and in
my main library.

I’d also like to see just the articles I’ve marked “Reading”. Sometimes I’d
want that list for my whole library, and sometimes just for one collection. If
I finish an article and mark it “Read” in one collection, it should drop off
the “Reading” list in the other one too.

Give me a design proposal [use $ca-design-proposal].
```

## 3. Archive and restore

```text
There are articles I’d like to put aside for a while. I’m thinking of adding
an archive. When I archive an article, I want it out of my main library and
out of the collections I’m browsing. I’d like to be able to open the archive
and find it there when I’m ready to come back to it.

For example, I might be halfway through an article that’s in both
“Food and cooking” and “Weekend reading”. I’ve marked it “Reading” and left
myself a note about where I stopped. Suppose I archive it today. When I
restore it, I’d expect it back in my library and in both collections. I should
be able to click the same title to open the original link, see my note, and
carry on with the article still marked “Reading”. This functionality should
work even if the app is restarted between archiving and restoring.

Give me a design proposal [use $ca-design-proposal].

I’d also like to know how I can check that everything comes back when I
restore one.
```
