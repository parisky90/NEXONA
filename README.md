I want to create a SaaS app for CV management. It should feature a minimal and visually appealing dashboard where the core operations will take place. On the main dashboard, there should be a list of uploaded CVs that have not yet been reviewed.

I want the user to be able to import files either through upload or drag-and-drop from their computer. These files will be in PDF or Word format. Most files will be in Greek or English. Once uploaded, the system should automatically extract and fill in specific fields and store both the filled information and the CV file itself.

The fields that should be automatically populated are:

First Name

Last Name

Age

Phone Number

Email

Education

Languages

Seminars

Work Experience

Date of CV submission

The user should have the option to manually edit any of these fields, and to add a custom field named "Position", which represents the job position(s) the candidate is interested in (can be more than one).

There should be an option to delete a candidate from the dashboard. On the main dashboard, the only visible data should be:

Full Name

Position(s)

Submission Date

When clicking on a candidate, it should navigate to a detailed view showing all the above fields, and the full CV (as uploaded, either PDF or Word). The view should include all necessary buttons like Delete, Back to Dashboard, Undo, etc.

Once a candidate is viewed from the main dashboard, there should be two options: Accept or Reject.

If Rejected, the candidate should move to a new layout called "Rejected Candidates", maintaining the same structure (only showing full name, clickable to see details and CV). The same functionality (delete, back, etc.) must be present.

If Accepted, the candidate should be moved to another layout called "Accepted CVs" with the same structure (name, date, and position). Clicking the name should show fields + CV.

When a candidate is rejected, an automated email should be sent with the following message (translated and refined in Greek):

«Το βιογραφικό σας εξετάστηκε. Ευχαριστούμε πολύ για το ενδιαφέρον σας, αλλά προς το παρόν δεν θα προχωρήσουμε σε συνεργασία. Το βιογραφικό σας θα διατηρηθεί στη βάση μας για ενδεχόμενη μελλοντική συνεργασία.»

From the Accepted CVs layout, the user can either:

Reject the candidate (send to Rejected Candidates and send the automated email), or

Move the candidate to a new layout called Interested CVs.

In the Interested CVs layout, the structure remains the same (name, position, submission date), and when opening a candidate, all the fields and the CV are visible again. There should be two options:

Interview

Reject (moves the candidate to Rejected Candidates and sends the email)

If Interview is selected, the candidate is moved to a layout named Interview Candidates, keeping the same structure (name, submission date, position).

In the Interview Candidates layout, the HR can add:

Interview date,

Time,

Location

using a calendar/time picker.

If the candidate declines the interview, they are moved to a layout called Candidate Declined, with the same structure and fields + ability to add a note (e.g., why they declined).

One hour before the interview, a reminder message should appear on the main dashboard saying something like:

“You have an interview in one hour with [Candidate Name] at [Location].”

After the interview:

If it happened, the user can confirm it and the candidate is moved to a layout called Evaluation.

If it didn’t happen, the user is given two options:

Reschedule interview

Reject (moves candidate to Rejected and sends the email)

In the Evaluation layout:

Show Full Name

Interview Date (instead of submission date)

Position

Clicking opens all fields, CV, and extra fields for:

Comments

Notes

Evaluation

There should be two options:

Make Offer (moves candidate to Offer Made layout)

Reject (moves to Rejected Candidates and sends the email)

In the Offer Made layout:

Structure remains the same: name, position, interview date

Clicking on candidate shows all info: fields, CV, notes/comments, and offer details

When the candidate replies:

If they accept, move them to a final layout called Hired Candidates with all available info

If they reject, move them to Candidate Declined layout (same as earlier)

Regardless of the stage the candidate is in, all fields should be editable, with the ability to save updates and add/edit notes and comments.

All candidates should be stored persistently in the layout they're currently in.

If a rejected candidate re-submits a new CV in the future, the system should detect this and notify the user, then link them to the candidate’s history so the full journey is visible.

The candidate journey from submission to final decision should be trackable and viewable (e.g., "Submitted → Accepted CV → Rejected" etc.).

In every layout, I want the structure and design to be consistent.

In every layout, there should be a search bar that allows the user to search for any candidate by First Name, Last Name, or Position. The search results should update the visible list dynamically.
