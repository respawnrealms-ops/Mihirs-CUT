# Mihis Cut studio

This local edition is based on PeakCut by Haziq Ahmed Qasmi. The original MIT licence and third-party notices remain in LICENSE and studio/models. The new frames and compositor are original code; no Yizerge code or proprietary assets are bundled.

Open Options when adding a video, or the Clips section of a creator’s Setup, then expand **Mihis Studio**. Finished clips have the same panel in their editor. Save creator changes to use the profile on future videos and live clips. Existing clips keep their saved profile until re-made.

- Choose 9:16, 1:1, 4:5, 16:9 or 3:4. Solo, split, PiP, trio and wide-shot split layouts support up to three manual source framing boxes. Load the original source in a clip’s studio, choose Shot 1/2/3, and drag a rectangle. Numeric boxes use fractions from 0 to 1. PiP has rectangle, rounded and circle masks. Swap reverses the framing boxes.
- Fifteen caption styles combine with six caption motions. Load timed words to edit spelling, timing, bold, italic, colour and boxes. SRT/ASS import estimates word times within each subtitle line; review them. Download SRT reflects the keep ranges. Caption times are relative to the original clip start, before cuts.
- Fifteen frame templates include light/dark social cards, a hook card, news, poll, comment, quote, code/notes, editorial, podcast, gaming, spotlight, review and announcement. Profile, subline, ticker, logo and watermark are editable. No verification or creator endorsement is inferred.
- Choose plain colour, gradient, blurred video or your own image, with dim, blur, padding, rounded corners, dividers and a panel shadow. White/cream/black canvas layouts place the full video in the middle, the hook above and captions below.
- The media library accepts images, audio and video up to 100 MB each. Add a music bed with speech ducking and an optional final riser, timed original pop/ping/whoosh/click sounds or your own audio, panel replacements, timed B-roll, and text/emoji/image stickers. B-roll keeps the source speech. Panel media and music loop; select a file offset for each panel.
- Keep ranges remove unwanted sections and join the remainder. Timed overlays and sound cues use the final joined output clock. Captions are remapped automatically. All keep ranges must be ordered and within the clip.
- Export 720p, 1080p or 2160p (4K), with source frame rate up to 60 or 24/30/60. 4K enlarges lower-resolution sources. Software is the reliable default for transparent compositions on older Intel graphics; explicit NVENC/AMF/QSV falls back to CPU if unavailable. Render time depends on the PC. A follow ribbon slides in near the end, and an optional outro adds an end card.
- Browser drafts and up to 50 undo/redo states keep editing work locally. Restore saved draft loads a previous browser draft. Save and re-make applies a clip edit; Preview makes only a three-second draft. Previews never enter the posting queue. Ctrl/Cmd-Z and Ctrl/Cmd-Y operate studio history outside text inputs. Space plays the loaded source; I/O set trim points outside text inputs.
- Light, dark and system themes are in the bottom-right theme selector.

Live recording, AI providers and posting continue to use the existing configuration. Environment names, the database, sessions and stored media stay compatible with PeakCut. Existing scheduled posts are not changed. A re-made clip does not automatically upload again.

Run with `python -m studio.server`. Run checks with `python tests/run.py` in an isolated copy without a real .env or data folder.

## Reference card templates

The Frame tab now has a live layout preview, a template gallery, and profile name, handle, photo, optional blue check, headline and supporting line controls. X Light and X Dark place your profile and headline above the centred video, with subtitles below it. Breaking News adds an editable red news bar, headline panel, strapline and optional ticker. Its LIVE badge is off until you enable it. TikTok Hook adds an editable hook label and yellow subtitles. These are independent designs; no reference-site code, logos or private footage are bundled.

Choose a background type, two colours and gradient direction, or use Blue night, Sunset, Violet or Ocean. Padding is shown as a percentage of the reference canvas width: 5% equals 54 reference pixels. Changes appear in the layout preview; Render preview in a finished clip checks the actual video and timed captions. Save creator Setup for future clips. Re-make existing clips to apply changes to their saved profile.

## Long YouTube compilations

On Home, keep **Make → Shorts — existing workflow** for the existing Shorts process. Shorts still use #Shorts and the existing Shorts links.

For a separate long upload, select **Make → Long YouTube highlight compilation**, then choose a 20, 30 or 40 minute target. Supply a finished video longer than the target using a link or Upload video. Each submitted source produces one compilation. The app transcribes the source, asks your configured AI to rank sections, selects highlights, and joins them in source order. Whole sections are retained, so the target is approximate within the 20–40 minute range. This mode requires a working AI service. Active live capture continues through the existing Shorts workflow.

The default is a 16:9 YouTube video canvas with captions off. Open Options and Mihis Studio to add a frame, profile, background or captions. Switching back to Shorts restores the earlier Shorts choices. A long source and export can need several GB and substantial processing time; render work is kept on the app drive.

A completed compilation is marked **Compilation**. Review its content and post text, then use Post with your connected YouTube account. These compilations do not auto-post, do not automatically add #Shorts, and return a regular YouTube watch link. Instagram and TikTok accounts cannot be chosen for these long compilations. Stop compilation cancels the current compilation; previously made videos and scheduled Shorts are preserved.
## Caption corrections and source credit

Open a finished clip and use **Edit caption text**. Its saved timed words load automatically. Change spelling, word timing or styling, then press **Apply caption changes**. To change the overall look, choose Caption style and press **Apply changes to video**. These actions render the video again and do not upload it again. Changing the caption style selects that style's own animation; you can then choose a separate animation in Mihis Studio if wanted. The video stays beside the controls on desktop.

Cards default to **Profile on the video → Source channel — automatic**. The name, handle and photo come from the original video's channel, independently of the connected posting account. The public channel photo is cached in the current user's private media library. Existing cards made with the old destination-account default pick up source credit when re-made. Choose **Custom profile** to type a name and handle or choose your own photo. Uploaded files without channel metadata can use their assigned source creator or a custom profile. If a public lookup fails, known source details remain; no unrelated posting identity is substituted.

## Raised video panels

In Mihis Studio → Frame → Background & spacing, enable **3D light border**. The video gets rounded corners, a soft cast shadow, a coloured halo and a directional bevel. **Rim light colour** and **Glow strength** adjust the lighting. The effect surrounds the panel and does not tint or blur the footage. It also works with multiple panels and circular picture in picture. Render preview checks the final video; Apply changes to video saves it. Existing cards without this setting retain their earlier appearance.

## Resuming a long compilation

If a long compilation stops, use **Resume compilation** on its error card. It reuses the downloaded source and saved transcript. Highlight scores are now saved as each batch finishes. Missing scores are retried one section at a time; completed scores are kept if the AI remains unavailable. Resuming uses only scores that match the current source sections. The app does not invent scores for missing answers. Only the owner can resume a job, and an active or still-stopping compilation cannot be queued twice. Review the finished video before posting.
