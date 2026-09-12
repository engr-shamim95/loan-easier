LOAN_AGREEMENT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body { font-family: 'Arial', sans-serif; margin: 40px; color: #2D3748; font-size: 14px; }
        h1 { color: #1A365D; text-align: center; font-size: 24px; margin-bottom: 5px; }
        h2 { color: #4A5568; text-align: center; font-size: 14px; font-weight: normal; font-style: italic; margin-top: 0; margin-bottom: 20px; }
        h3 { color: #2B6CB0; font-size: 16px; border-bottom: 1px solid #E2E8F0; padding-bottom: 5px; margin-top: 30px; }
        hr { border: 0; border-top: 2px solid #2B6CB0; margin-bottom: 20px; }
        table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
        .meta-table td { padding: 10px; background-color: #F7FAFC; border: 1px solid #CBD5E0; vertical-align: top; }
        .data-table td { padding: 8px; border-bottom: 1px solid #E2E8F0; }
        .data-table td:first-child { width: 30%; font-weight: bold; }
        .audit-badge { background-color: #C6F6D5; border: 1px solid #38A169; color: #276749; text-align: center; padding: 10px; font-weight: bold; font-size: 12px; margin: 20px 0; }
        .signatures { margin-top: 40px; }
        .signatures td { padding-top: 30px; }
        .page-break { page-break-before: always; }
    </style>
</head>
<body>
    <h1>{{ lender_name }}</h1>
    <h2>{{ lender_address }}</h2>
    <hr>
    {% if project_type == 'training' %}
    <h3>প্রশিক্ষণ ভাতা প্রাপ্তি ও অঙ্গীকারনামা</h3>
    <h4 style="text-align: center; color: #4A5568; margin-top: -10px;">সেলাই প্রশিক্ষণ ভাতা বিতরণ</h4>
    {% else %}
    <h3>অফিসিয়াল ঋণ চুক্তি ও অঙ্গীকারনামা</h3>
    <h4 style="text-align: center; color: #4A5568; margin-top: -10px;">সাধারণ বাণিজ্যিক ঋণ প্রদান ও জামানত চুক্তি</h4>
    {% endif %}

    <table class="meta-table">
        <tr>
            <td><b>{% if project_type == 'training' %}রেকর্ড{% else %}চুক্তির{% endif %} ক্রমিক নং:</b> {{ loan.serial_number }}</td>
            <td><b>সম্পাদনের তারিখ:</b> {{ loan.verified_at[:10] if loan.verified_at else current_date }}</td>
        </tr>
        <tr>
            <td><b>রেকর্ড আইডি:</b> #{{ loan.id }}</td>
            <td><b>যাচাইকরণ স্ট্যাটাস:</b> {{ 'যাচাইকৃত (VERIFIED)' if loan.verified else 'খসড়া (DRAFT)' }}</td>
        </tr>
    </table>

    {% if project_type == 'training' %}
    <h3>১. প্রশিক্ষণার্থীর বিবরণ</h3>
    {% else %}
    <h3>১. ঋণগ্রহীতার বিবরণ</h3>
    {% endif %}
    <table class="data-table">
        <tr><td>পূর্ণ নাম:</td><td>{{ loan.name }}</td></tr>
        <tr><td>মোবাইল নম্বর:</td><td>{{ loan.mobile }}</td></tr>
        <tr><td>ঠিকানা:</td><td>{{ loan.address or 'প্রদান করা হয়নি' }}</td></tr>
    </table>

    {% if project_type == 'training' %}
    <h3>২. ভাতার পরিমাণ ও প্রদানের মাধ্যম</h3>
    <table class="data-table" style="background-color: #EDF2F7;">
        <tr><td>অনুমোদিত ভাতার পরিমাণ:</td><td><b>৳ {{ '{:,.2f}'.format(loan.amount) }}</b></td></tr>
        <tr><td>প্রদানের মাধ্যম:</td><td>সরাসরি ইলেকট্রনিক ফান্ড ট্রান্সফার বা নগদ</td></tr>
    </table>

    <h3>৩. প্রশিক্ষণার্থীর অঙ্গীকারনামা</h3>
    <p>
        নিম্নস্বাক্ষরকারী প্রশিক্ষণার্থী এতদ্বারা ঘোষণা করছেন যে, তিনি মহিলা বিষয়ক অধিদপ্তর কর্তৃক আয়োজিত সেলাই প্রশিক্ষণ কোর্সে নিয়মিত অংশগ্রহণ করেছেন এবং উপরোক্ত প্রশিক্ষণ ভাতা <b>৳ {{ '{:,.2f}'.format(loan.amount) }}</b> বুঝে পেয়েছেন। প্রশিক্ষণলব্ধ জ্ঞান কাজে লাগিয়ে তিনি আত্মকর্মসংস্থানের মাধ্যমে স্বাবলম্বী হওয়ার চেষ্টা করবেন।
    </p>
    {% else %}
    <h3>২. ঋণের পরিমাণ এবং আর্থিক শর্তাবলী</h3>
    <table class="data-table" style="background-color: #EDF2F7;">
        <tr><td>অনুমোদিত ঋণের পরিমাণ:</td><td><b>৳ {{ '{:,.2f}'.format(loan.amount) }}</b></td></tr>
        <tr><td>প্রদানের মাধ্যম:</td><td>সরাসরি ইলেকট্রনিক ফান্ড ট্রান্সফার বা নগদ</td></tr>
        <tr><td>পরিশোধের সময়সূচী:</td><td>সংযুক্ত সময়সূচী অনুযায়ী নিয়মিত মাসিক কিস্তিতে পরিশোধযোগ্য।</td></tr>
    </table>

    <h3>৩. অঙ্গীকারনামা এবং আইনি শর্তাবলী</h3>
    <p>
        মূল্য প্রাপ্তির শর্তে, নিম্নস্বাক্ষরকারী ঋণগ্রহীতা ঋণ প্রদানকারী প্রতিষ্ঠানকে মূল ঋণ <b>৳ {{ '{:,.2f}'.format(loan.amount) }}</b> এবং প্রযোজ্য সুদ প্রদান করতে অঙ্গীকারবদ্ধ। ঋণগ্রহীতা এই চুক্তির একটি স্বাক্ষরিত কপি গ্রহণের কথা স্বীকার করছেন এবং নিশ্চিত করছেন যে প্রদানকৃত নথিপত্র থেকে সংগৃহীত তথ্যাদি যাচাই করা হয়েছে এবং তা সম্পূর্ণ নির্ভুল।
    </p>
    {% endif %}

    <div class="audit-badge">
        ✓ হিউম্যান-ইন-দ্য-লুপ (HITL) দ্বারা যাচাইকৃত | OCR ইঞ্জিন: {{ loan.ocr_engine_used }} | যাচাইকরণের সময়: {{ loan.verified_at or 'রিভিউর পর যাচাইকৃত' }}
    </div>

    <h3>৪. স্বাক্ষরসমূহ</h3>
    <table class="signatures">
        <tr>
            <td width="50%">
                <b>{% if project_type == 'training' %}প্রশিক্ষণার্থী:{% else %}ঋণগ্রহীতা:{% endif %}</b><br><br><br>
                স্বাক্ষর: ___________________________<br>
                নাম: {{ loan.name }}<br>
                তারিখ: {{ loan.verified_at[:10] if loan.verified_at else current_date }}
            </td>
            <td width="50%">
                <b>অনুমোদিত কর্মকর্তা:</b><br><br><br>
                স্বাক্ষর: ___________________________<br>
                নাম: ___________________________<br>
                তারিখ: {{ loan.verified_at[:10] if loan.verified_at else current_date }}
            </td>
        </tr>
    </table>
</body>
</html>
"""

BATCH_SUMMARY_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body { font-family: 'Arial', sans-serif; margin: 40px; color: #2D3748; font-size: 12px; }
        h1 { color: #1A365D; text-align: center; font-size: 24px; margin-bottom: 5px; }
        h2 { color: #4A5568; text-align: center; font-size: 14px; font-weight: normal; margin-top: 0; margin-bottom: 20px; }
        hr { border: 0; border-top: 2px solid #2B6CB0; margin-bottom: 20px; }
        h3 { color: #2B6CB0; font-size: 16px; border-bottom: 1px solid #E2E8F0; padding-bottom: 5px; margin-top: 30px; }
        table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
        .meta-table td { padding: 10px; background-color: #F7FAFC; border: 1px solid #CBD5E0; vertical-align: top; font-size: 14px; }
        .summary-table th { background-color: #1A365D; color: white; padding: 8px; text-align: left; }
        .summary-table td { padding: 8px; border-bottom: 1px solid #E2E8F0; }
        .summary-table tr:last-child td { font-weight: bold; background-color: #EDF2F7; }
        .page-break { page-break-before: always; }
    </style>
</head>
<body>
    <h1>{{ lender_name }}</h1>
    <h2>{{ lender_address }}</h2>
    <hr>
    {% if project_type == 'training' %}
    <h3 style="text-align: center;">সেলাই প্রশিক্ষণ ভাতা বিতরণ ব্যাচ সামারি</h3>
    {% else %}
    <h3 style="text-align: center;">BATCH EXECUTION SUMMARY</h3>
    {% endif %}
    <h4 style="text-align: center; color: #4A5568; margin-top: -10px;">Batch Reference: {{ batch_id }} | Generated: {{ current_date }}</h4>

    <table class="meta-table">
        <tr>
            <td><b>Batch Identifier:</b> {{ batch_id }}</td>
            <td><b>Total Records:</b> {{ loans|length }}</td>
        </tr>
        <tr>
            <td>
            {% if project_type == 'training' %}
                <b>Total Allowance Sum:</b> BDT {{ '{:,.2f}'.format(total_amount) }}
            {% else %}
                <b>Total Principal Sum:</b> BDT {{ '{:,.2f}'.format(total_amount) }}
            {% endif %}
            </td>
            <td><b>Audit Status:</b> HITL Verified Batch</td>
        </tr>
    </table>

    {% if project_type == 'training' %}
    <h3>ব্যাচ প্রশিক্ষণ ভাতা শিডিউল এবং সামারি</h3>
    {% else %}
    <h3>ব্যাচ লোন শিডিউল এবং সামারি (BATCH LOAN SCHEDULE & SUMMARY)</h3>
    {% endif %}
    <table class="summary-table">
        <tr>
            <th>ক্রমিক নং (Serial)</th>
            <th>{% if project_type == 'training' %}নাম (Trainee Name){% else %}নাম (Borrower Name){% endif %}</th>
            <th>মোবাইল (Mobile)</th>
            <th>ঠিকানা (Address)</th>
            <th>{% if project_type == 'training' %}ভাতার পরিমাণ (Allowance){% else %}পরিমাণ (Amount){% endif %}</th>
        </tr>
        {% for loan in loans %}
        <tr>
            <td>{{ loan.serial_number }}</td>
            <td>{{ loan.name }}</td>
            <td>{{ loan.mobile }}</td>
            <td>{{ loan.address or 'প্রদান করা হয়নি' }}</td>
            <td>{{ '{:,.2f}'.format(loan.amount) }}</td>
        </tr>
        {% endfor %}
        <tr>
            <td>{{ loans|length }} records</td>
            <td></td>
            <td></td>
            <td>TOTAL_AMOUNT</td>
            <td>{{ '{:,.2f}'.format(total_amount) }}</td>
        </tr>
    </table>
    
    {% for loan in loans %}
    <div class="page-break"></div>
    {{ loan_htmls[loop.index0] | safe }}
    {% endfor %}
</body>
</html>
"""
