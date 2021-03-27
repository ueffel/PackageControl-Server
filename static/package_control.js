if (!String.prototype.endsWith)
{
    String.prototype.endsWith = function(suffix)
    {
        return this.indexOf(suffix, this.length - suffix.length) !== -1;
    };
}

function sortPackages(button)
{
    if (!button || !button.hasAttribute("data-sort-field"))
    {
        return;
    }
    sortBy = button.getAttribute("data-sort-field");

    let packages = [].slice.call(document.getElementsByClassName("package"));
    if (!button.hasAttribute("data-sort-dir") || button.getAttribute("data-sort-dir") == "asc")
    {
        sortDirection = "asc";
    }
    else
    {
        sortDirection = "desc";
    }
    packages.sort(function (left, right)
    {
        let left_value;
        let right_value;

        switch(sortBy)
        {
            case "name":
                left_value = left.getElementsByClassName("package--name")[0].innerHTML.toLowerCase();
                right_value = right.getElementsByClassName("package--name")[0].innerHTML.toLowerCase();
                break;
            case "updated":
                left_elements = left.getElementsByClassName("package--last-updated");
                right_elements = right.getElementsByClassName("package--last-updated");
                left_value = left_elements.length > 0 ? new Date(left_elements[0].getAttribute("datetime")) : new Date(0);
                right_value = right_elements.length > 0 ? new Date(right_elements[0].getAttribute("datetime")) : new Date(0);
                break;
            case "stars":
                left_stars = left.getElementsByClassName("package--stars");
                right_stars = right.getElementsByClassName("package--stars");
                left_value = left_stars.length > 0 ? parseInt(left_stars[0].innerHTML) : 0;
                right_value = right_stars.length > 0 ? parseInt(right_stars[0].innerHTML) : 0;
                break;
            case "author":
                left_value = left.getElementsByClassName("package--author")[0].innerHTML.toLowerCase();
                right_value = right.getElementsByClassName("package--author")[0].innerHTML.toLowerCase();
                break;
            case "added":
                left_value = new Date(left.getElementsByClassName("package--added")[0].getAttribute("datetime"));
                right_value = new Date(right.getElementsByClassName("package--added")[0].getAttribute("datetime"));
                break;
            case "downloads":
                left_downloads = left.getElementsByClassName("package--downloads");
                right_downloads = right.getElementsByClassName("package--downloads");
                left_value = left_downloads.length > 0 ? parseInt(left_downloads[0].innerHTML) : 0;
                right_value = right_downloads.length > 0 ? parseInt(right_downloads[0].innerHTML) : 0;
                break;
            default:
                break;
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

        // console.log(left_value + " " + right_value + " -> " + cmp);

        if (sortDirection == "desc")
        {
            return cmp;
        }
        else
        {
            return cmp * -1;
        }
    });

    let packagesBefore = document.getElementsByClassName("package");
    for (let i = 1; i < packagesBefore.length; i++)
    {
        let parent = packagesBefore[i].parentNode;
        parent.insertBefore(packages[i], parent.firstChild.nextSibling);
    }
    button.setAttribute("data-sort-dir", sortDirection == "asc" ? "desc" : "asc");
}

function makeRelativeTime(date)
{
    let now = Date.now();
    let diff = now - date;

    if (diff > 7 * 3600 * 24 * 1000)
    {
        return date.toLocaleDateString();
    }
    else
    {
        let days = Math.floor(diff / (24 * 60 * 60 * 1000));
        let hours = Math.floor(diff / (60 * 60 * 1000));
        let minutes = Math.floor(diff / (60 * 1000));
        let seconds = Math.floor(diff / 1000);
        let date_str;

        if (days > 0)
        {
            date_str = days + " days";
        }
        else if (hours > 0)
        {
            date_str = hours + " hours";
        }
        else if (minutes > 0)
        {
            date_str = minutes + " minutes"
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
