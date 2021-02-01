const urlParams = new URLSearchParams(location.search);

const season = urlParams.get('season');
const year = urlParams.get('year');

function setDefaultSelected(obj, val) {
    for (i=0;i<obj.options.length;i++){
        if (obj.options[i].value === val){
            obj.options[i].selected = true;
            break;
        }
    }
    return;
}

setDefaultSelected(document.getElementById('season'), season);
setDefaultSelected(document.getElementById('year'), year);

function onSearch(){
    const query = document.getElementById('song-search').value;
    const parent = document.getElementById('search-results');
    fetch(`/search?query=${query}`).then(res => {
        if (res.status == 401){
            // show modal asking to refresh
            $('#addSongModal').modal('hide');
            $('#tokenExpiredModal').modal('show');
        }
        return res.json();
    }).then(data => {
        console.log(data);
        parent.innerText = ""; //clear search
        parent.style.display = "block";
        const list = data['tracks']['items'];
        list.forEach((suggestion)=> {
            const songDiv = document.createElement('div');
            songDiv.style.display = "flex";
            songDiv.style.alignItems = "center";
            songDiv.style.justifyContent = "center";
            const textDiv = document.createElement('p');
            textDiv.innerText = suggestion['name'] + ' by ' + suggestion['artists'][0]['name'];
            textDiv.style.margin = "auto 1rem";
            const addButton = document.createElement('button');
            addButton.className = "styled-button";
            addButton.type = "button";
            addButton.innerText = "+";
            addButton.onclick = () => {
                // make time period show up and search results disappear
                document.getElementById('song-search').value = suggestion['name'];
                document.getElementById('song-name').value = suggestion['name'];
                document.getElementById('song-artist').value = suggestion['artists'][0]['name'];
                document.getElementById('song-id').value = suggestion['id'];
                document.getElementById('song-image').value = suggestion['album']['images'][suggestion['album']['images'].length - 1]['url'];
                document.getElementById('song-preview').value = suggestion['preview_url'];
                document.getElementById('song-link').value = suggestion['external_urls']['spotify'];
                document.getElementById('search-results').style.display = "none";
                document.getElementById('period-picker').style.display = "block";
            };

            songDiv.appendChild(addButton);
            songDiv.appendChild(textDiv);
            parent.appendChild(songDiv);
        });
    });
}

function onSave(id) {
    try{
        // stop audio if playing
        document.getElementById(`play-${id}`).pause();
    } catch (e) {
        console.log(e);
    }
    fetch(`/save?id=${id}`).then(res=> {
        const idsToScan = [`save-button-empty-${id}`, `save-button-filled-${id}`, `saved-tile-${id}`];
        //update it to be filled
        for (const idName of idsToScan) {
            if (document.getElementById(idName)) {
                if (document.getElementById(idName).style.display !== "none") {
                    document.getElementById(idName).style.display = "none";
                } else {
                    document.getElementById(idName).style.display = "inline";
                }
            }
        }
    });
}

function onAudioToggle(id){
    if (!document.getElementById(`play-${id}`).paused){
        document.getElementById(`play-${id}`).pause();
        // change to play button
        document.getElementById(`toggle-play-${id}`).innerHTML = "<i class=\"bi bi-play\"></i>";

    }else {
        document.getElementById(`play-${id}`).play();
        // change to pause button
        document.getElementById(`toggle-play-${id}`).innerHTML = "<i class=\"bi bi-pause\"></i>";
    }
}