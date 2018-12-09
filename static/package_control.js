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
            left_value = left.getElementsByTagName('td')[sortColumn].textContent;
        }
        right_value = right.getElementsByTagName('td')[sortColumn].getAttribute('data-time')
        if (!right_value)
        {
            right_value = right.getElementsByTagName('td')[sortColumn].textContent;
        }
        let cmp = left_value.localeCompare(right_value);
        console.log(left_value);
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
    let date_str;
    let now = Date.now();
    let diff = now - date;

    if (diff >= 3600 * 23 * 1000)
    {
        return date.toLocaleString();
    }
    else
    {
        let hours = new Date(diff).getUTCHours();
        let minutes = new Date(diff).getUTCMinutes();
        let seconds = new Date(diff).getSeconds();
        date_str = "";
        if (hours > 0)
        {
            date_str += hours + " hours";
        }
        else if (minutes > 0)
        {
            date_str += minutes + " minutes";
        }
        else if (seconds > 0)
        {
            date_str += seconds + " seconds";
        }
        date_str += " ago";
        return date_str;
    }
}

window.onload = function()
{
    let table = document.getElementsByTagName('table')[0];
    let rows =  [].slice.call(table.getElementsByTagName('tr')).slice(1);
    for(let i = 0; i < rows.length; i++)
    {
        let tempdate = new Date(rows[i].getElementsByTagName('td')[3].getAttribute('data-time'));
        tempdate.setTime(tempdate.getTime() - new Date().getTimezoneOffset()*60000)
        if (tempdate && tempdate.getTime())
        {
            rows[i].getElementsByTagName('td')[3].innerHTML = makeRelativeTime(tempdate);
        }
        tempdate = new Date(rows[i].getElementsByTagName('td')[4].getAttribute('data-time'));
        tempdate.setTime(tempdate.getTime() - new Date().getTimezoneOffset()*60000)
        if (tempdate && tempdate.getTime())
        {
            rows[i].getElementsByTagName('td')[4].innerHTML = makeRelativeTime(tempdate);
        }
    }
};
