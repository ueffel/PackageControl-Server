if (!String.prototype.endsWith)
{
    String.prototype.endsWith = function(suffix)
    {
        return this.indexOf(suffix, this.length - suffix.length) !== -1;
    };
}

function sortTable(header, sortDirection)
{
    if (!header)
    {
        return;
    }

    let table = header.parentElement.parentElement.parentElement;
    let rows =  [].slice.call(table.getElementsByTagName('tr')).slice(1);
    if (sortDirection == undefined)
    {
        sortDirection = 'asc';
        if (header.innerHTML.endsWith(' ▲'))
        {
            sortDirection = 'desc';
        }
    }
    let sortColumn = -1
    for (let i = 0; i < header.parentElement.children.length; i++)
    {
        if (header == header.parentElement.children[i])
        {
            sortColumn = i
            break;
        }
    }
    if (sortColumn == -1)
    {
        return;
    }
    rows.sort(function(left, right)
    {
        left_value = left.getElementsByTagName('td')[sortColumn].getAttribute('data-time');
        if (!left_value)
        {
            left_value = parseInt(left.getElementsByTagName('td')[sortColumn].getAttribute('data-int'));
            if (isNaN(left_value))
            {
                left_value = left.getElementsByTagName('td')[sortColumn].textContent;
            }
        }
        right_value = right.getElementsByTagName('td')[sortColumn].getAttribute('data-time')
        if (!right_value)
        {
            right_value = parseInt(right.getElementsByTagName('td')[sortColumn].getAttribute('data-int'));
            if (isNaN(right_value)) {
                right_value = right.getElementsByTagName('td')[sortColumn].textContent;
            }
        }
        let cmp;
        if (left_value < right_value)
        {
            cmp = -1;
        }
        else if (right_value < left_value)
        {
            cmp = 1;
        }
        else
        {
            cmp = 0;
        }

        if (sortDirection == 'desc')
        {
            return cmp;
        }
        else
        {
            return cmp * -1;
        }
    });
    let rowsBefore = table.getElementsByTagName('tr');
    for (let i = 1; i < rowsBefore.length; i++)
    {
        let parent = rowsBefore[i].parentNode;
        parent.insertBefore(rows[i-1], parent.firstChild.nextSibling);
    }

    let headers = table.getElementsByTagName('th');
    for(let i = 0; i < headers.length; i++)
    {
        headers[i].innerHTML = headers[i].innerHTML.replace(' ▲', '').replace(' ▼', '');
    }
    header.innerHTML += sortDirection == 'asc' ? ' ▲' : ' ▼';
}

function makeRelativeTime(date)
{
    let now = Date.now();
    let diff = now - date;

    if (diff >= 3600 * 24 * 1000)
    {
        return date.toLocaleString();
    }
    else
    {
        let hours = new Date(diff).getUTCHours();
        let minutes = new Date(diff).getUTCMinutes();
        let seconds = new Date(diff).getSeconds();
        let date_str;

        if (hours > 0)
        {
            date_str = hours + " hours";
            if (minutes > 0)
            {
                date_str += " " + minutes + " minutes";
            }
        }
        else if (minutes > 0)
        {
            date_str = minutes + " minutes"
            if (seconds > 0)
            {
                date_str +=  " " + seconds + " seconds";
            }
        }
        else
        {
            date_str = seconds + " seconds";
        }
        date_str += " ago";
        return date_str;
    }
}

function showTooltip(event, field_id)
{
    let field_tooltip = document.getElementById(field_id + "_tooltip");
    field_tooltip.style.left = event.clientX + "px";
    field_tooltip.style.top = event.clientY + "px";
}
