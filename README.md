# Kuku Promo Finder

**Problem 1: Find the Promos.** Give the tool a timestamped microdrama screenplay. It recommends continuous 20–60 second clips, with the episode, exact in/out timestamps, opening hook, cliffhanger and a one-line reason to post each clip.

[Open the Streamlit app](https://ramhaneesh-kuku-promos.streamlit.app/) and upload a screenplay. To try it without the assignment pack, download the [original sample screenplay](demo/episode-001-original.txt). The app shows the top three promos for the selected script.

## Run locally

From the repository root, using PowerShell and Python 3.12:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open [localhost:8501](http://localhost:8501). The offline CLI uses only the Python standard library, so you can skip the package installation if you only want the CLI.

## Find promos from the command line

Run the included sample first. The command prints its top picks and writes the results to a separate folder so you can compare them with the submission.

```powershell
.\.venv\Scripts\python.exe run.py --input "demo/episode-001-original.txt" --output_dir outputs_demo
```

For an unseen screenplay, replace the sample path with your timestamped `.txt` file. For a full show, use `--batch` with a folder containing the episode files. The assignment pack is private and must be supplied locally.

```powershell
.\.venv\Scripts\python.exe run.py --batch "I Married a Broken Soldier. He was a Duke" --output_dir outputs_rerun
```

## Scoring modes

**Offline (default).** Python checks event boundaries and clip duration, scores tension cues in the first and last three seconds, and removes overlapping picks. The posting list favors higher scores, with episode variety, duration and standalone context helping resolve ties. Quiet reveals can score poorly when they lack the words or punctuation the rules look for.

**Gemini (optional).** Set `GEMINI_API_KEY` and `GEMINI_MODEL` in a local, git-ignored `.env` file. Use `GEMINI_MODEL=gemini-3.5-flash-lite`. For your own Streamlit deployment, put the API key in Streamlit Secrets. Visitors can use the hosted app without a key. Add `--mode llm` to a CLI command, or choose `LLM_ENHANCED` in the app and click **Score shortlisted clips with Gemini**. This sends the shortlisted excerpts for one episode together in one request. Gemini evaluates the opening and ending and supplies a rationale. Successful reviews use Gemini’s score for ranking and keep the offline baseline. If scoring fails, the affected clips retain their offline scores.

## Submission outputs

The offline full-pack run evaluated **34,065** eligible windows across **50 episodes** in **0.68 seconds**. It produced:

| File | What it contains |
| --- | --- |
| [all_promos.json](outputs/all_promos.json) | All 525 shortlisted promos, covering all 50 episodes. Each entry includes timestamps, duration, hook, cliffhanger, rationale, score and scoring mode. |
| [top_ranked_promos.csv](outputs/top_ranked_promos.csv) | The show's 20 recommended promos to post first, in posting order, with a ranking reason for each. |

See the [solution document](SOLUTION_DOC.md) for the assumptions, ranking example and quality review.
