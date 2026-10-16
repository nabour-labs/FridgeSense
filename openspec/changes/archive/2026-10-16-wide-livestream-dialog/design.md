# Design

- Add `size?: "default" | "wide"` to `Sheet` rather than a free-form `className`, so dialog widths stay a small, named set.
- `"wide"` swaps `max-w-md` for `sm:max-w-3xl`. Below `sm` the sheet is already `w-full`, so phones are unaffected. 768 px gives a ~720 × 405 video, large enough to read labels while still leaving the backdrop visible on a 1280 px laptop.
- The video box keeps `aspect-video` and `object-contain`, so it scales with the wider card.
- Tests check the dialog element's class (`sm:max-w-3xl` for Livestream, `max-w-md` for others); jsdom has no layout, so the class is the observable contract.
